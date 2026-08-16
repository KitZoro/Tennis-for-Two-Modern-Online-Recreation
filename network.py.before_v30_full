from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

from config import (
    CONFIG_DIR, TRUST_FILE, MAX_PACKET_SIZE, MAX_PACKETS_PER_SECOND,
    CONNECT_TIMEOUT, NETWORK_STALL_WARNING, NETWORK_DEAD_TIMEOUT,
    PAIR_DISCOVERY_PORT, PAIR_DISCOVERY_TIMEOUT, OUTGOING_QUEUE_MAX,
)

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
except ImportError:
    x509 = None


CONFIG_DIR = Path.home() / ".config" / "tennis_for_two"
TRUST_FILE = CONFIG_DIR / "trusted_hosts.json"


def normalize_security_code(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch in "0123456789ABCDEF")


def format_security_code(hex_value: str) -> str:
    compact = normalize_security_code(hex_value)[:16]
    return "-".join(compact[i:i + 4] for i in range(0, len(compact), 4))


def load_trusted_hosts() -> dict[str, str]:
    try:
        data = json.loads(TRUST_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): format_security_code(str(v)) for k, v in data.items()}
    except (OSError, ValueError, TypeError):
        pass
    return {}


def save_trusted_host(host: str, port: int, code: str) -> None:
    hosts = load_trusted_hosts()
    hosts[f"{host}:{port}"] = format_security_code(code)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TRUST_FILE.write_text(json.dumps(hosts, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


_clipboard_tk_root = None


def _get_tk_clipboard_root():
    """Keep a hidden Tk window alive so Linux retains clipboard ownership."""
    global _clipboard_tk_root
    if _clipboard_tk_root is not None:
        return _clipboard_tk_root
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update()
        _clipboard_tk_root = root
        return root
    except Exception:
        return None


def clipboard_set(text: str) -> tuple[bool, str]:
    """Copy to the desktop clipboard and verify another application can read it."""
    clean = str(text).strip()

    # Wayland: wl-copy owns and serves the real desktop clipboard.
    if shutil.which("wl-copy") and shutil.which("wl-paste"):
        try:
            subprocess.run(
                ["wl-copy", "--type", "text/plain;charset=utf-8"],
                input=clean,
                text=True,
                check=True,
                timeout=1.0,
            )
            check = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                check=True,
                timeout=1.0,
            )
            if check.stdout.strip() == clean:
                return True, "DESKTOP CLIPBOARD"
        except (OSError, subprocess.SubprocessError):
            pass

    # X11/Linux Mint: xclip places the value in CLIPBOARD, which Discord reads.
    if shutil.which("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-in"],
                input=clean,
                text=True,
                check=True,
                timeout=1.0,
            )
            check = subprocess.run(
                ["xclip", "-selection", "clipboard", "-out"],
                capture_output=True,
                text=True,
                check=True,
                timeout=1.0,
            )
            if check.stdout.strip() == clean:
                return True, "DESKTOP CLIPBOARD"
        except (OSError, subprocess.SubprocessError):
            pass

    if shutil.which("xsel"):
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=clean,
                text=True,
                check=True,
                timeout=1.0,
            )
            check = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True,
                text=True,
                check=True,
                timeout=1.0,
            )
            if check.stdout.strip() == clean:
                return True, "DESKTOP CLIPBOARD"
        except (OSError, subprocess.SubprocessError):
            pass

    # Tk is retained only as a fallback. It must verify by reading the value back.
    root = _get_tk_clipboard_root()
    if root is not None:
        try:
            root.clipboard_clear()
            root.clipboard_append(clean)
            root.update()
            if str(root.clipboard_get()).strip() == clean:
                return True, "SYSTEM CLIPBOARD"
        except Exception:
            pass

    # Pygame is the final fallback, but do not claim it is Discord-compatible.
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, clean.encode("utf-8") + b"\x00")
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw and clean in raw.decode("utf-8", errors="ignore"):
            return False, "GAME-ONLY CLIPBOARD"
    except pygame.error:
        pass

    return False, "DESKTOP CLIPBOARD UNAVAILABLE"


def clipboard_get() -> tuple[str, str]:
    """Read clipboard quickly without freezing the Pygame window."""
    root = _get_tk_clipboard_root()
    if root is not None:
        try:
            root.update()
            value = root.clipboard_get()
            if value:
                return str(value).strip(), "SYSTEM CLIPBOARD"
        except Exception:
            pass

    # Pygame is non-blocking, so try it before external commands.
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw:
            value = raw.decode("utf-8", errors="ignore").replace("\x00", "").strip()
            if value:
                return value, "PYGAME"
    except pygame.error:
        pass

    commands = []
    if shutil.which("wl-paste"):
        commands.append((["wl-paste", "--no-newline"], "WL-PASTE"))
    if shutil.which("xclip"):
        commands.append((["xclip", "-selection", "clipboard", "-o"], "XCLIP"))
    if shutil.which("xsel"):
        commands.append((["xsel", "--clipboard", "--output"], "XSEL"))

    for command, method in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=0.35,
            )
            value = result.stdout.strip()
            if value:
                return value, method
        except (OSError, subprocess.SubprocessError):
            pass

    return "", "CLIPBOARD EMPTY"


@dataclass
class TailscalePeerInfo:
    name: str
    address: str
    online: bool


def tailscale_snapshot() -> tuple[str, list[TailscalePeerInfo], str]:
    """Return this device name, visible peers, and a short status message."""
    if shutil.which("tailscale") is None:
        return "", [], "TAILSCALE COMMAND NOT FOUND"

    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=True,
        )
        data = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return "", [], "TAILSCALE STATUS UNAVAILABLE"

    self_data = data.get("Self") if isinstance(data, dict) else {}
    if not isinstance(self_data, dict):
        self_data = {}

    self_name = str(
        self_data.get("HostName")
        or self_data.get("DNSName")
        or "THIS COMPUTER"
    ).rstrip(".")

    peers: list[TailscalePeerInfo] = []
    raw_peers = data.get("Peer", {}) if isinstance(data, dict) else {}
    iterable = raw_peers.values() if isinstance(raw_peers, dict) else raw_peers

    if isinstance(iterable, (list, tuple)) or hasattr(iterable, "__iter__"):
        for raw in iterable:
            if not isinstance(raw, dict):
                continue
            addresses = raw.get("TailscaleIPs") or []
            address = ""
            if isinstance(addresses, list):
                # Prefer IPv4 because this game's transport uses AF_INET.
                for candidate in addresses:
                    candidate = str(candidate)
                    if "." in candidate:
                        address = candidate
                        break
                if not address and addresses:
                    address = str(addresses[0])
            if not address or ":" in address:
                continue

            name = str(
                raw.get("HostName")
                or raw.get("DNSName")
                or address
            ).rstrip(".")
            online = bool(raw.get("Online", False))
            peers.append(TailscalePeerInfo(name=name, address=address, online=online))

    peers.sort(key=lambda p: (not p.online, p.name.lower()))
    return self_name, peers, "TAILSCALE CONNECTED"


def trusted_code_for_peer(peer: TailscalePeerInfo, port: int) -> str:
    trusted = load_trusted_hosts()
    return (
        trusted.get(f"name:{peer.name}:{port}", "")
        or trusted.get(f"{peer.address}:{port}", "")
    )


def save_trusted_peer(peer: TailscalePeerInfo, port: int, code: str) -> None:
    formatted = format_security_code(code)
    hosts = load_trusted_hosts()
    hosts[f"name:{peer.name}:{port}"] = formatted
    hosts[f"{peer.address}:{port}"] = formatted
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TRUST_FILE.write_text(json.dumps(hosts, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass



class PairingDiscovery:
    """Exchange the short TLS fingerprint over the already-authenticated Tailscale path.

    This removes manual code entry while keeping the actual game session on TLS 1.3.
    The discovery socket binds only to the local Tailscale IPv4 address when one is
    available, so it is not exposed on ordinary LAN/public interfaces.
    """

    def __init__(self, pairing_code_getter):
        self.pairing_code_getter = pairing_code_getter
        self.running = True
        self.sock: Optional[socket.socket] = None
        self.local_tailscale_ip = self._local_tailscale_ipv4()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @staticmethod
    def _local_tailscale_ipv4() -> str:
        if shutil.which("tailscale") is None:
            return ""
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=True,
            )
            return result.stdout.strip().splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError, IndexError):
            return ""

    def _serve(self) -> None:
        if not self.local_tailscale_ip:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock = sock
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.local_tailscale_ip, PAIR_DISCOVERY_PORT))
            sock.settimeout(0.5)

            while self.running:
                try:
                    data, addr = sock.recvfrom(512)
                except socket.timeout:
                    continue
                except OSError:
                    break

                # Only answer requests from the Tailscale CGNAT range.
                if not str(addr[0]).startswith("100."):
                    continue

                try:
                    request = json.loads(data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue

                if not isinstance(request, dict) or request.get("type") != "tft_pair_request":
                    continue

                code = format_security_code(self.pairing_code_getter() or "")
                if len(normalize_security_code(code)) != 16:
                    continue

                response = {
                    "type": "tft_pair_response",
                    "code": code,
                }
                try:
                    sock.sendto(
                        json.dumps(response, separators=(",", ":")).encode("utf-8"),
                        addr,
                    )
                except OSError:
                    pass
        except OSError:
            pass
        finally:
            if self.sock is not None:
                try:
                    self.sock.close()
                except OSError:
                    pass

    def request_code(self, peer_ip: str) -> str:
        """Ask a selected Tailscale peer for its current short TLS fingerprint."""
        if not self.local_tailscale_ip or not peer_ip.startswith("100."):
            return ""

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.local_tailscale_ip, 0))
            sock.settimeout(PAIR_DISCOVERY_TIMEOUT)
            request = {
                "type": "tft_pair_request",
            }
            sock.sendto(
                json.dumps(request, separators=(",", ":")).encode("utf-8"),
                (peer_ip, PAIR_DISCOVERY_PORT),
            )
            data, addr = sock.recvfrom(512)
            if addr[0] != peer_ip:
                return ""
            response = json.loads(data.decode("utf-8"))
            if not isinstance(response, dict) or response.get("type") != "tft_pair_response":
                return ""
            code = format_security_code(str(response.get("code", "")))
            if len(normalize_security_code(code)) != 16:
                return ""
            return code
        except (OSError, ValueError, UnicodeDecodeError):
            return ""
        finally:
            sock.close()

    def close(self) -> None:
        self.running = False
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass


# -----------------------------
# TLS certificate generation
# -----------------------------

def require_crypto() -> None:
    if x509 is None:
        raise RuntimeError(
            "The 'cryptography' package is required. Install with:\n"
            "python3 -m pip install --user cryptography"
        )


def generate_ephemeral_certificate() -> tuple[Path, Path, str]:
    require_crypto()
    from datetime import datetime, timedelta, timezone

    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Tennis for Two temporary host"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=24))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    temp_dir = Path(tempfile.mkdtemp(prefix="tft_tls_"))
    cert_path = temp_dir / "host_cert.pem"
    key_path = temp_dir / "host_key.pem"

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    der = cert.public_bytes(serialization.Encoding.DER)
    fingerprint = hashlib.sha256(der).hexdigest().upper()
    short = format_security_code(fingerprint)
    return cert_path, key_path, short


def cert_fingerprint_from_socket(sock: ssl.SSLSocket) -> str:
    der = sock.getpeercert(binary_form=True)
    full = hashlib.sha256(der).hexdigest().upper()
    return format_security_code(full)


# -----------------------------
# Secure framed transport
# -----------------------------

class SecurePeer:
    """Threaded framed transport for the live match.

    v27 deliberately keeps both reads *and writes* off the Pygame/game thread.
    send() only enqueues a payload and returns immediately; the writer thread is
    the only place that can wait on a congested TLS/Tailscale socket.
    """

    def __init__(self, sock: ssl.SSLSocket):
        self.sock = sock
        # Wake periodically, but tolerate temporary Tailscale/ISP stalls.
        self.sock.settimeout(2.0)
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

        self.alive = True
        self.inbox: "queue.Queue[dict]" = queue.Queue()
        self.outbox: "queue.Queue[dict]" = queue.Queue(maxsize=OUTGOING_QUEUE_MAX)
        self.send_seq = 0
        self.recv_seq = -1
        self.packet_times: list[float] = []
        self.last_received = time.monotonic()
        self.error_reason = ""
        self._death_lock = threading.Lock()

        # Telemetry used by diagnostics.py.
        self.packets_in = 0
        self.packets_out = 0
        self.max_outgoing_queue = 0
        self.last_send_stall_ms = 0.0

        try:
            self.remote_address = str(self.sock.getpeername()[0])
        except (OSError, TypeError, IndexError):
            self.remote_address = ""

        self.reader_thread = threading.Thread(target=self._reader, daemon=True, name="tft-net-reader")
        self.writer_thread = threading.Thread(target=self._writer, daemon=True, name="tft-net-writer")
        self.reader_thread.start()
        self.writer_thread.start()


    def _terminate(self, reason: str = "") -> None:
        """Atomically mark the peer dead and close the socket.

        Closing the socket is important: simply flipping ``alive`` can leave the
        other reader/writer thread (and the remote computer) waiting on a TLS
        connection that is already unusable.  Keep the first useful error so a
        secondary ``bad file descriptor`` does not overwrite the real cause.
        """
        with self._death_lock:
            if reason and not self.error_reason:
                self.error_reason = str(reason)
            was_alive = self.alive
            self.alive = False

        if was_alive:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass

    def fail(self, reason: str) -> None:
        self._terminate(reason or "Network connection failed")

    @property
    def seconds_since_packet(self) -> float:
        return max(0.0, time.monotonic() - self.last_received)

    @property
    def stalled(self) -> bool:
        return self.alive and self.seconds_since_packet >= NETWORK_STALL_WARNING

    @property
    def outgoing_queue_depth(self) -> int:
        return self.outbox.qsize()

    def _recv_exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size and self.alive:
            try:
                part = self.sock.recv(size - len(chunks))
            except (
                socket.timeout,
                BlockingIOError,
                ssl.SSLWantReadError,
                ssl.SSLWantWriteError,
            ):
                # Windows may report WSAEWOULDBLOCK / WinError 10035, while
                # OpenSSL can report WANT_READ/WANT_WRITE. These are temporary
                # "not ready yet" states, not lost connections.
                if self.seconds_since_packet >= NETWORK_DEAD_TIMEOUT:
                    raise ConnectionError(
                        f"No network traffic for {int(NETWORK_DEAD_TIMEOUT)} seconds"
                    )
                time.sleep(0.01)
                continue

            if not part:
                raise ConnectionError("Connection closed")
            chunks.extend(part)

        return bytes(chunks)

    def _reader(self) -> None:
        try:
            while self.alive:
                header = self._recv_exact(4)
                if len(header) != 4:
                    raise ConnectionError("Connection closed")
                size = struct.unpack("!I", header)[0]
                if size <= 0 or size > MAX_PACKET_SIZE:
                    raise ConnectionError("Invalid packet size")

                raw = self._recv_exact(size)
                if len(raw) != size:
                    raise ConnectionError("Connection closed")
                data = json.loads(raw.decode("utf-8"))

                if not isinstance(data, dict):
                    continue
                seq = data.get("seq")
                payload = data.get("payload")
                if not isinstance(seq, int) or seq <= self.recv_seq:
                    continue
                if not isinstance(payload, dict):
                    continue

                now = time.monotonic()
                self.packet_times = [t for t in self.packet_times if now - t < 1.0]
                if len(self.packet_times) >= MAX_PACKETS_PER_SECOND:
                    raise ConnectionError("Packet rate limit exceeded")
                self.packet_times.append(now)

                self.recv_seq = seq
                self.last_received = now
                self.packets_in += 1
                self.inbox.put(payload)
        except (OSError, ssl.SSLError, ValueError, json.JSONDecodeError, ConnectionError) as exc:
            if self.alive:
                self._terminate(str(exc) or exc.__class__.__name__)

    def _writer(self) -> None:
        try:
            while self.alive:
                try:
                    payload = self.outbox.get(timeout=0.25)
                except queue.Empty:
                    continue

                envelope = {"seq": self.send_seq, "payload": payload}
                self.send_seq += 1
                raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
                if len(raw) > MAX_PACKET_SIZE:
                    self.outbox.task_done()
                    continue
                packet = struct.pack("!I", len(raw)) + raw

                stall_started: Optional[float] = None
                while self.alive:
                    try:
                        self.sock.sendall(packet)
                        self.packets_out += 1
                        if stall_started is not None:
                            self.last_send_stall_ms = (time.monotonic() - stall_started) * 1000.0
                        else:
                            self.last_send_stall_ms = 0.0
                        break
                    except (
                        socket.timeout,
                        BlockingIOError,
                        ssl.SSLWantReadError,
                        ssl.SSLWantWriteError,
                    ):
                        if stall_started is None:
                            stall_started = time.monotonic()
                        if time.monotonic() - stall_started >= NETWORK_DEAD_TIMEOUT:
                            raise ConnectionError(
                                f"Outgoing network stalled for {int(NETWORK_DEAD_TIMEOUT)} seconds"
                            )
                        time.sleep(0.01)
                        continue

                self.outbox.task_done()
        except (OSError, ssl.SSLError, ConnectionError) as exc:
            if self.alive:
                self._terminate(str(exc) or exc.__class__.__name__)

    def send(self, payload: dict) -> bool:
        """Queue one payload without ever blocking the game/render thread."""
        if not self.alive:
            return False
        if not isinstance(payload, dict):
            return False
        try:
            # Copy the top level so a caller cannot mutate the queued object.
            self.outbox.put_nowait(dict(payload))
            self.max_outgoing_queue = max(self.max_outgoing_queue, self.outbox.qsize())
            return True
        except queue.Full:
            self._terminate("Outgoing network queue overflow")
            return False

    def poll_all(self) -> list[dict]:
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def close(self) -> None:
        self._terminate()


@dataclass
class ConnectResult:
    peer: Optional[SecurePeer] = None
    error: Optional[str] = None
    fingerprint: Optional[str] = None


class ConnectJob:
    def __init__(self):
        self.cancel = threading.Event()
        self.done = threading.Event()
        self.result = ConnectResult()
        self.thread: Optional[threading.Thread] = None

    def start_host(self, port: int, bind_host: str = "0.0.0.0") -> None:
        self.thread = threading.Thread(target=self._host_worker, args=(port, bind_host), daemon=True)
        self.thread.start()

    def _host_worker(self, port: int, bind_host: str = "0.0.0.0") -> None:
        listener = None
        temp_paths = []
        try:
            cert_path, key_path, fingerprint = generate_ephemeral_certificate()
            temp_paths = [cert_path, key_path, cert_path.parent]
            self.result.fingerprint = fingerprint

            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3
            context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((bind_host, port))
            listener.listen(1)
            listener.settimeout(0.25)

            while not self.cancel.is_set():
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                conn.settimeout(CONNECT_TIMEOUT)
                tls = None
                handshake_deadline = time.monotonic() + CONNECT_TIMEOUT
                while not self.cancel.is_set():
                    try:
                        if tls is None:
                            tls = context.wrap_socket(
                                conn,
                                server_side=True,
                                do_handshake_on_connect=False,
                            )
                        tls.do_handshake()
                        break
                    except (
                        socket.timeout,
                        BlockingIOError,
                        ssl.SSLWantReadError,
                        ssl.SSLWantWriteError,
                    ):
                        if time.monotonic() >= handshake_deadline:
                            raise TimeoutError("TLS handshake timed out")
                        time.sleep(0.01)
                        continue

                if tls is not None:
                    self.result.peer = SecurePeer(tls)
                    break
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            if "10035" in message or "would block" in message.lower():
                message = "Network temporarily busy; please try again"
            self.result.error = message
        finally:
            if listener:
                try:
                    listener.close()
                except OSError:
                    pass
            self.done.set()

    def start_join(self, host: str, port: int, expected_fingerprint: str) -> None:
        self.thread = threading.Thread(
            target=self._join_worker,
            args=(host, port, expected_fingerprint),
            daemon=True,
        )
        self.thread.start()

    def _join_worker(self, host: str, port: int, expected_fingerprint: str) -> None:
        sock = None
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
            if self.cancel.is_set():
                sock.close()
                return

            tls = context.wrap_socket(
                sock,
                server_hostname=host,
                do_handshake_on_connect=False,
            )

            handshake_deadline = time.monotonic() + CONNECT_TIMEOUT
            while not self.cancel.is_set():
                try:
                    tls.do_handshake()
                    break
                except (
                    socket.timeout,
                    BlockingIOError,
                    ssl.SSLWantReadError,
                    ssl.SSLWantWriteError,
                ):
                    if time.monotonic() >= handshake_deadline:
                        raise TimeoutError("TLS handshake timed out")
                    time.sleep(0.01)
                    continue
            else:
                tls.close()
                return

            if self.cancel.is_set():
                tls.close()
                return

            actual = cert_fingerprint_from_socket(tls)
            expected = format_security_code(expected_fingerprint)
            if normalize_security_code(expected) != normalize_security_code(actual):
                tls.close()
                raise RuntimeError(
                    "Security code mismatch.\n"
                    f"Expected: {expected}\n"
                    f"Received: {actual}"
                )
            self.result.peer = SecurePeer(tls)
            self.result.fingerprint = actual
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            if "10035" in message or "would block" in message.lower():
                message = "Network temporarily busy; please try again"
            if not self.cancel.is_set():
                self.result.error = message
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        finally:
            self.done.set()


from __future__ import annotations

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
NETWORK = ROOT / "network.py"
DIAGNOSTICS = ROOT / "diagnostics.py"
CONFIG = ROOT / "config.py"

MARKER = "# v30 NETWORK STABILITY PATCH: single-thread TLS I/O"
NEW_SECURE_PEER = '# v30 NETWORK STABILITY PATCH: single-thread TLS I/O\nclass SecurePeer:\n    """TLS/TCP peer whose SSLSocket is driven by one I/O thread.\n\n    The v30 transport used one thread for recv() and a second thread for send()\n    on the same SSLSocket. This patch serializes all TLS reads and writes onto\n    one network thread. The game thread only queues dictionaries and polls\n    received dictionaries.\n\n    The on-wire format is unchanged: this is still TCP + TLS, protocol 29.\n    """\n\n    def __init__(self, sock: ssl.SSLSocket):\n        self.sock = sock\n        self.sock.setblocking(False)\n\n        try:\n            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)\n        except OSError:\n            pass\n\n        try:\n            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)\n            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)\n        except OSError:\n            pass\n\n        try:\n            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)\n            if hasattr(socket, "TCP_KEEPIDLE"):\n                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 15)\n            if hasattr(socket, "TCP_KEEPINTVL"):\n                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)\n            if hasattr(socket, "TCP_KEEPCNT"):\n                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)\n        except OSError:\n            pass\n\n        self.alive = True\n        self.inbox: "queue.Queue[dict]" = queue.Queue()\n        self.outbox: "queue.Queue[dict]" = queue.Queue(maxsize=OUTGOING_QUEUE_MAX)\n\n        self.send_seq = 0\n        self.recv_seq = -1\n        self.packet_times: list[float] = []\n        self.last_received = time.monotonic()\n        self.last_sent = time.monotonic()\n\n        self.error_reason = ""\n        self.termination_source = ""\n        self._death_lock = threading.Lock()\n\n        self.packets_in = 0\n        self.packets_out = 0\n        self.max_outgoing_queue = 0\n        self.last_send_stall_ms = 0.0\n        self.send_buffer_bytes = 0\n\n        self._recv_buffer = bytearray()\n        self._send_buffer = bytearray()\n        self._send_buffer_packet_count = 0\n        self._send_stall_started: Optional[float] = None\n\n        try:\n            self.remote_address = str(self.sock.getpeername()[0])\n        except (OSError, TypeError, IndexError):\n            self.remote_address = ""\n\n        self.io_thread = threading.Thread(\n            target=self._io_loop,\n            daemon=True,\n            name="tft-net-io",\n        )\n        self.reader_thread = self.io_thread\n        self.writer_thread = self.io_thread\n        self.io_thread.start()\n\n    def _terminate(self, reason: str = "", source: str = "") -> None:\n        with self._death_lock:\n            if reason and not self.error_reason:\n                self.error_reason = str(reason)\n            if source and not self.termination_source:\n                self.termination_source = str(source)\n            was_alive = self.alive\n            self.alive = False\n\n        if was_alive:\n            try:\n                self.sock.shutdown(socket.SHUT_RDWR)\n            except (OSError, ssl.SSLError):\n                pass\n            try:\n                self.sock.close()\n            except (OSError, ssl.SSLError):\n                pass\n\n    def fail(self, reason: str) -> None:\n        self._terminate(reason or "Network connection failed", "game_fail")\n\n    @property\n    def seconds_since_packet(self) -> float:\n        return max(0.0, time.monotonic() - self.last_received)\n\n    @property\n    def stalled(self) -> bool:\n        return self.alive and self.seconds_since_packet >= NETWORK_STALL_WARNING\n\n    @property\n    def outgoing_queue_depth(self) -> int:\n        return self.outbox.qsize() + (1 if self._send_buffer else 0)\n\n    def _accept_payload(self, data: dict) -> None:\n        if not isinstance(data, dict):\n            return\n\n        seq = data.get("seq")\n        payload = data.get("payload")\n        if not isinstance(seq, int) or seq <= self.recv_seq:\n            return\n        if not isinstance(payload, dict):\n            return\n\n        now = time.monotonic()\n        self.packet_times = [t for t in self.packet_times if now - t < 1.0]\n        if len(self.packet_times) >= MAX_PACKETS_PER_SECOND:\n            raise ConnectionError("Packet rate limit exceeded")\n        self.packet_times.append(now)\n\n        self.recv_seq = seq\n        self.last_received = now\n        self.packets_in += 1\n        self.inbox.put(payload)\n\n    def _parse_received_bytes(self) -> None:\n        while True:\n            if len(self._recv_buffer) < 4:\n                return\n\n            size = struct.unpack("!I", self._recv_buffer[:4])[0]\n            if size <= 0 or size > MAX_PACKET_SIZE:\n                raise ConnectionError(f"Invalid packet size: {size}")\n\n            total = 4 + size\n            if len(self._recv_buffer) < total:\n                return\n\n            raw = bytes(self._recv_buffer[4:total])\n            del self._recv_buffer[:total]\n\n            try:\n                data = json.loads(raw.decode("utf-8"))\n            except (UnicodeDecodeError, json.JSONDecodeError) as exc:\n                raise ConnectionError(f"Invalid network JSON: {exc}") from exc\n\n            self._accept_payload(data)\n\n    def _serialize_outgoing(self) -> None:\n        if self._send_buffer:\n            return\n\n        batch: list[dict] = []\n        while len(batch) < 32:\n            try:\n                batch.append(self.outbox.get_nowait())\n            except queue.Empty:\n                break\n\n        if not batch:\n            return\n\n        framed: list[bytes] = []\n        valid_count = 0\n\n        try:\n            for payload in batch:\n                envelope = {"seq": self.send_seq, "payload": payload}\n                self.send_seq += 1\n                raw = json.dumps(envelope, separators=(",", ":")).encode("utf-8")\n                if len(raw) > MAX_PACKET_SIZE:\n                    continue\n                framed.append(struct.pack("!I", len(raw)) + raw)\n                valid_count += 1\n        finally:\n            for _ in batch:\n                self.outbox.task_done()\n\n        if framed:\n            self._send_buffer.extend(b"".join(framed))\n            self._send_buffer_packet_count = valid_count\n            self.send_buffer_bytes = len(self._send_buffer)\n\n    def _try_receive(self) -> bool:\n        progressed = False\n\n        for _ in range(8):\n            try:\n                chunk = self.sock.recv(65536)\n                if not chunk:\n                    raise ConnectionError("Remote closed TCP/TLS connection")\n\n                self._recv_buffer.extend(chunk)\n                progressed = True\n                self._parse_received_bytes()\n\n                pending = 0\n                try:\n                    pending = self.sock.pending()\n                except (OSError, ssl.SSLError):\n                    pass\n                if pending <= 0:\n                    break\n\n            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):\n                break\n\n        return progressed\n\n    def _try_send(self) -> bool:\n        if not self._send_buffer:\n            self._send_stall_started = None\n            self.last_send_stall_ms = 0.0\n            self.send_buffer_bytes = 0\n            return False\n\n        try:\n            sent = self.sock.send(self._send_buffer)\n            if sent <= 0:\n                raise ConnectionError("TLS socket stopped accepting data")\n\n            del self._send_buffer[:sent]\n            self.send_buffer_bytes = len(self._send_buffer)\n            self.last_sent = time.monotonic()\n\n            if self._send_stall_started is not None:\n                self.last_send_stall_ms = (\n                    time.monotonic() - self._send_stall_started\n                ) * 1000.0\n            else:\n                self.last_send_stall_ms = 0.0\n\n            if not self._send_buffer:\n                self.packets_out += self._send_buffer_packet_count\n                self._send_buffer_packet_count = 0\n                self._send_stall_started = None\n\n            return True\n\n        except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):\n            if self._send_stall_started is None:\n                self._send_stall_started = time.monotonic()\n            return False\n\n    def _io_loop(self) -> None:\n        try:\n            while self.alive:\n                self._serialize_outgoing()\n\n                progress = False\n                progress |= self._try_receive()\n                progress |= self._try_send()\n\n                now = time.monotonic()\n\n                if self.seconds_since_packet >= NETWORK_DEAD_TIMEOUT:\n                    raise ConnectionError(\n                        f"No network traffic for {int(NETWORK_DEAD_TIMEOUT)} seconds"\n                    )\n\n                if (\n                    self._send_stall_started is not None\n                    and now - self._send_stall_started >= NETWORK_DEAD_TIMEOUT\n                ):\n                    raise ConnectionError(\n                        f"Outgoing network stalled for {int(NETWORK_DEAD_TIMEOUT)} seconds"\n                    )\n\n                if not progress:\n                    time.sleep(0.002)\n\n        except ConnectionError as exc:\n            if self.alive:\n                message = str(exc) or exc.__class__.__name__\n                source = "remote_eof" if "Remote closed" in message else "transport"\n                self._terminate(message, source)\n\n        except (OSError, ssl.SSLError, ValueError) as exc:\n            if self.alive:\n                self._terminate(\n                    f"{exc.__class__.__name__}: {str(exc) or \'network I/O failure\'}",\n                    "transport_exception",\n                )\n\n        except Exception as exc:\n            if self.alive:\n                self._terminate(\n                    f"{exc.__class__.__name__}: {str(exc) or \'unexpected network failure\'}",\n                    "transport_exception",\n                )\n\n    def send(self, payload: dict) -> bool:\n        if not self.alive or not isinstance(payload, dict):\n            return False\n\n        try:\n            self.outbox.put_nowait(dict(payload))\n            self.max_outgoing_queue = max(\n                self.max_outgoing_queue,\n                self.outbox.qsize(),\n            )\n            return True\n\n        except queue.Full:\n            self._terminate(\n                "Outgoing network queue overflow",\n                "outbox_overflow",\n            )\n            return False\n\n    def poll_all(self) -> list[dict]:\n        out = []\n        while True:\n            try:\n                out.append(self.inbox.get_nowait())\n            except queue.Empty:\n                return out\n\n    def close(self) -> None:\n        self._terminate("Local match closed", "local_close")\n\n\n'

def fail(message: str) -> None:
    print()
    print("PATCH NOT APPLIED")
    print(message)
    print()
    input("Press Enter to close...")
    raise SystemExit(1)

def backup(path: Path) -> None:
    backup_path = path.with_name(path.name + ".before_network_stability_patch")
    if path.exists() and not backup_path.exists():
        shutil.copy2(path, backup_path)

for required in (NETWORK, DIAGNOSTICS, CONFIG, ROOT / "main.py", ROOT / "rollback.py"):
    if not required.exists():
        fail(f"Missing {required.name}. Put this patch beside main.py.")

config_text = CONFIG.read_text(encoding="utf-8", errors="replace")
if not re.search(r"(?m)^FPS\s*=\s*120\s*$", config_text):
    fail("This patch expects the v30 FULL 120 FPS build.")
if not re.search(r"(?m)^PROTOCOL_VERSION\s*=\s*29\s*$", config_text):
    fail("This patch expects v30 protocol 29.")

network_text = NETWORK.read_text(encoding="utf-8")
if MARKER in network_text:
    print()
    print("The v30 Network Stability Patch is already applied.")
    print()
    input("Press Enter to close...")
    raise SystemExit(0)

class_start = network_text.find("class SecurePeer:")
class_end = network_text.find("@dataclass\nclass ConnectResult:")
if class_start < 0 or class_end < 0 or class_end <= class_start:
    fail("Could not locate SecurePeer in network.py. No files were changed.")

diagnostics_text = DIAGNOSTICS.read_text(encoding="utf-8")

old_header = (
    '            "outgoing_queue", "max_outgoing_queue", "last_send_stall_ms",\n'
    '            "seconds_since_packet", "stalled", "error_reason",\n'
)
new_header = (
    '            "outgoing_queue", "max_outgoing_queue", "send_buffer_bytes",\n'
    '            "last_send_stall_ms", "seconds_since_packet", "stalled",\n'
    '            "termination_source", "error_reason",\n'
)

old_row = (
    '            getattr(peer, "max_outgoing_queue", 0) if peer else 0,\n'
    '            f"{getattr(peer, \'last_send_stall_ms\', 0.0):.1f}" if peer else "0",\n'
    '            f"{peer.seconds_since_packet:.3f}" if peer else "0",\n'
    '            int(bool(peer.stalled)) if peer else 0,\n'
    '            getattr(peer, "error_reason", "") if peer else "",\n'
)
new_row = (
    '            getattr(peer, "max_outgoing_queue", 0) if peer else 0,\n'
    '            getattr(peer, "send_buffer_bytes", 0) if peer else 0,\n'
    '            f"{getattr(peer, \'last_send_stall_ms\', 0.0):.1f}" if peer else "0",\n'
    '            f"{peer.seconds_since_packet:.3f}" if peer else "0",\n'
    '            int(bool(peer.stalled)) if peer else 0,\n'
    '            getattr(peer, "termination_source", "") if peer else "",\n'
    '            getattr(peer, "error_reason", "") if peer else "",\n'
)

if old_header not in diagnostics_text or old_row not in diagnostics_text:
    fail("diagnostics.py is not the expected v30 FULL version. No files were changed.")

backup(NETWORK)
backup(DIAGNOSTICS)

patched_network = network_text[:class_start] + NEW_SECURE_PEER + network_text[class_end:]
patched_diagnostics = diagnostics_text.replace(old_header, new_header, 1)
patched_diagnostics = patched_diagnostics.replace(old_row, new_row, 1)

NETWORK.write_text(patched_network, encoding="utf-8")
DIAGNOSTICS.write_text(patched_diagnostics, encoding="utf-8")

try:
    compile(patched_network, str(NETWORK), "exec")
    compile(patched_diagnostics, str(DIAGNOSTICS), "exec")
except Exception as exc:
    net_backup = NETWORK.with_name(NETWORK.name + ".before_network_stability_patch")
    diag_backup = DIAGNOSTICS.with_name(DIAGNOSTICS.name + ".before_network_stability_patch")
    if net_backup.exists():
        shutil.copy2(net_backup, NETWORK)
    if diag_backup.exists():
        shutil.copy2(diag_backup, DIAGNOSTICS)
    fail(f"Syntax check failed and backups were restored: {exc}")

print()
print("==============================================")
print(" v30 NETWORK STABILITY PATCH APPLIED")
print("==============================================")
print("Protocol remains 29.")
print("TCP/TLS remains the gameplay transport.")
print("Story mode and control settings are untouched.")
print()
print("Main change:")
print("  TLS recv + send now run on ONE I/O thread.")
print()
print("New diagnostics:")
print("  termination_source")
print("  send_buffer_bytes")
print("  clearer remote EOF vs local transport errors")
print()
print("Both computers should apply this patch before the next test.")
print()
print("Backups:")
print("  network.py.before_network_stability_patch")
print("  diagnostics.py.before_network_stability_patch")
print()
print("Then launch normally with: python3 main.py")
print()
input("Press Enter to close...")

from __future__ import annotations

import queue
import random
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional

from network import ConnectJob, SecurePeer


@dataclass(frozen=True)
class NetworkTestPreset:
    key: str
    label: str
    rtt_ms: float
    jitter_ms: float = 0.0
    stall_chance: float = 0.0
    stall_ms: float = 0.0

    @property
    def one_way_ms(self) -> float:
        return self.rtt_ms / 2.0

    @property
    def description(self) -> str:
        parts = [f"~{int(self.rtt_ms)} ms RTT"]
        if self.jitter_ms:
            parts.append(f"±{int(self.jitter_ms)} ms jitter/leg")
        if self.stall_chance:
            parts.append(f"{int(self.stall_chance * 100)}% +{int(self.stall_ms)} ms stalls")
        return " • ".join(parts)


NETWORK_TEST_PRESETS = (
    NetworkTestPreset("1", "LOCAL CLEAN", 0.0),
    NetworkTestPreset("2", "100 ms", 100.0, 8.0),
    NetworkTestPreset("3", "250 ms", 250.0, 18.0),
    NetworkTestPreset("4", "430 ms — ARGENTINA", 430.0, 25.0),
    NetworkTestPreset("5", "430 ms + JITTER", 430.0, 65.0),
    NetworkTestPreset("6", "430 ms — NASTY", 430.0, 80.0, 0.03, 550.0),
)


class DelayedPeer:
    """Latency/jitter shim around the real TLS SecurePeer.

    Payloads still travel through SecurePeer, TLS 1.3, framing, reader/writer
    threads and rollback. This wrapper only delays when an outbound payload is
    handed to the real transport. Delay is kept in-order to resemble TCP.
    """

    def __init__(self, peer: SecurePeer, preset: NetworkTestPreset, seed: int):
        self.peer = peer
        self.preset = preset
        self.random = random.Random(seed)
        self.pending: "queue.Queue[tuple[float, dict]]" = queue.Queue(maxsize=4096)
        self._alive = True
        self._last_due = 0.0
        self._max_pending = 0
        self._thread = threading.Thread(target=self._pump, daemon=True, name="tft-net-test-delay")
        self._thread.start()

    @property
    def alive(self) -> bool:
        return self._alive and self.peer.alive

    @alive.setter
    def alive(self, value: bool) -> None:
        self._alive = bool(value)
        if not value:
            self.peer.close()

    def fail(self, reason: str) -> None:
        self._alive = False
        self.peer.fail(reason)

    @property
    def error_reason(self) -> str:
        return self.peer.error_reason

    @error_reason.setter
    def error_reason(self, value: str) -> None:
        self.peer.error_reason = value

    @property
    def seconds_since_packet(self) -> float:
        return self.peer.seconds_since_packet

    @property
    def stalled(self) -> bool:
        return self.peer.stalled

    @property
    def remote_address(self) -> str:
        return self.peer.remote_address

    @property
    def packets_in(self) -> int:
        return self.peer.packets_in

    @property
    def packets_out(self) -> int:
        return self.peer.packets_out

    @property
    def outgoing_queue_depth(self) -> int:
        return self.pending.qsize() + self.peer.outgoing_queue_depth

    @property
    def max_outgoing_queue(self) -> int:
        return max(self._max_pending, self.peer.max_outgoing_queue)

    @property
    def last_send_stall_ms(self) -> float:
        return self.peer.last_send_stall_ms

    def _schedule_time(self) -> float:
        now = time.monotonic()
        delay_ms = self.preset.one_way_ms
        if self.preset.jitter_ms:
            delay_ms += self.random.uniform(-self.preset.jitter_ms, self.preset.jitter_ms)
        if self.preset.stall_chance and self.random.random() < self.preset.stall_chance:
            delay_ms += self.preset.stall_ms

        due = now + max(0.0, delay_ms) / 1000.0
        # TCP is ordered. A later payload cannot overtake an earlier payload.
        due = max(due, self._last_due + 0.00001)
        self._last_due = due
        return due

    def send(self, payload: dict) -> bool:
        if not self.alive or not isinstance(payload, dict):
            return False
        try:
            self.pending.put_nowait((self._schedule_time(), dict(payload)))
            self._max_pending = max(self._max_pending, self.pending.qsize())
            return True
        except queue.Full:
            self.fail("Network test delay queue overflow")
            return False

    def _pump(self) -> None:
        while self._alive and self.peer.alive:
            try:
                due, payload = self.pending.get(timeout=0.20)
            except queue.Empty:
                continue

            while self._alive and self.peer.alive:
                remaining = due - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.01))

            if self._alive and self.peer.alive:
                if not self.peer.send(payload):
                    self._alive = False
            self.pending.task_done()

    def poll_all(self) -> list[dict]:
        return self.peer.poll_all()

    def close(self) -> None:
        self._alive = False
        self.peer.close()


class LoopbackPairJob:
    """Create a real TLS host+guest pair on 127.0.0.1 in the background."""

    def __init__(self):
        self.done = threading.Event()
        self.error = ""
        self.host_peer: Optional[SecurePeer] = None
        self.guest_peer: Optional[SecurePeer] = None
        self.port = 0
        self.stage = "STARTING"
        self.cancel = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="tft-loopback-setup")

    def start(self) -> None:
        self._thread.start()

    def cancel_setup(self) -> None:
        self.cancel.set()

    @staticmethod
    def _free_local_port() -> int:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])
        finally:
            probe.close()

    def _worker(self) -> None:
        host_job: Optional[ConnectJob] = None
        join_job: Optional[ConnectJob] = None
        try:
            self.port = self._free_local_port()
            host_job = ConnectJob()
            self.stage = "CREATING LOCAL TLS HOST"
            host_job.start_host(self.port, bind_host="127.0.0.1")

            deadline = time.monotonic() + 10.0
            while not host_job.result.fingerprint and not host_job.result.error:
                if self.cancel.is_set():
                    host_job.cancel.set()
                    return
                if time.monotonic() >= deadline:
                    raise TimeoutError("Local TLS host did not produce a pairing code")
                time.sleep(0.01)

            if host_job.result.error:
                raise RuntimeError(host_job.result.error)

            self.stage = "CONNECTING LOCAL TLS GUEST"
            if self.cancel.is_set():
                host_job.cancel.set()
                return

            join_job = ConnectJob()
            join_job.start_join("127.0.0.1", self.port, host_job.result.fingerprint or "")

            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if self.cancel.is_set():
                    host_job.cancel.set()
                    join_job.cancel.set()
                    return
                if host_job.done.is_set() and join_job.done.is_set():
                    break
                time.sleep(0.01)
            else:
                raise TimeoutError("Local TLS connection timed out")

            if host_job.result.error:
                raise RuntimeError(host_job.result.error)
            if join_job.result.error:
                raise RuntimeError(join_job.result.error)
            if host_job.result.peer is None or join_job.result.peer is None:
                raise RuntimeError("Local TLS pair was not created")

            self.host_peer = host_job.result.peer
            self.guest_peer = join_job.result.peer
            self.stage = "READY"
        except Exception as exc:
            self.error = str(exc) or exc.__class__.__name__
            self.stage = "FAILED"
            if host_job and host_job.result.peer:
                host_job.result.peer.close()
            if join_job and join_job.result.peer:
                join_job.result.peer.close()
        finally:
            if self.cancel.is_set():
                if host_job:
                    host_job.cancel.set()
                    if host_job.result.peer:
                        host_job.result.peer.close()
                if join_job:
                    join_job.cancel.set()
                    if join_job.result.peer:
                        join_job.result.peer.close()
                self.stage = "CANCELLED"
            self.done.set()

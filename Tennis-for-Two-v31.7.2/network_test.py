from __future__ import annotations

import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Optional

from config import NETWORK_DEAD_TIMEOUT, NETWORK_STALL_WARNING


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
            parts.append(
                f"{int(self.stall_chance * 100)}% +{int(self.stall_ms)} ms stalls"
            )
        return " • ".join(parts)


NETWORK_TEST_PRESETS = (
    NetworkTestPreset("1", "LOCAL CLEAN", 0.0),
    NetworkTestPreset("2", "100 ms", 100.0, 8.0),
    NetworkTestPreset("3", "250 ms", 250.0, 18.0),
    NetworkTestPreset("4", "430 ms — ARGENTINA", 430.0, 25.0),
    NetworkTestPreset("5", "430 ms + JITTER", 430.0, 65.0),
    NetworkTestPreset("6", "430 ms — NASTY", 430.0, 80.0, 0.03, 550.0),
)


class InMemoryPeer:
    """Socket-free peer used ONLY by the one-PC network simulator.

    It implements the same small interface RollbackSession expects, but moves
    dictionaries between two in-process inboxes instead of opening TCP/TLS.
    Real online play still uses network.py and TLS 1.3.
    """

    def __init__(self, name: str):
        self.name = name
        self.other: Optional["InMemoryPeer"] = None
        self.inbox: "queue.Queue[dict]" = queue.Queue()
        self.alive = True
        self.error_reason = ""
        self.last_received = time.monotonic()

        self.packets_in = 0
        self.packets_out = 0
        self.max_outgoing_queue = 0
        self.last_send_stall_ms = 0.0
        self.remote_address = "in-memory"

        self._lock = threading.Lock()

    def connect(self, other: "InMemoryPeer") -> None:
        self.other = other

    @property
    def seconds_since_packet(self) -> float:
        return max(0.0, time.monotonic() - self.last_received)

    @property
    def stalled(self) -> bool:
        return (
            self.alive
            and self.seconds_since_packet >= NETWORK_STALL_WARNING
        )

    @property
    def outgoing_queue_depth(self) -> int:
        return 0

    def send(self, payload: dict) -> bool:
        if not self.alive or not isinstance(payload, dict):
            return False

        other = self.other
        if other is None or not other.alive:
            self.fail("In-memory test peer is not available")
            return False

        # Top-level copy matches SecurePeer.send() behavior.
        copied = dict(payload)
        other.inbox.put(copied)
        other.packets_in += 1
        other.last_received = time.monotonic()
        self.packets_out += 1
        return True

    def poll_all(self) -> list[dict]:
        out: list[dict] = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out

    def fail(self, reason: str) -> None:
        with self._lock:
            if reason and not self.error_reason:
                self.error_reason = str(reason)
            self.alive = False

        # Mirror a real dead connection to the other endpoint so the test does
        # not leave one zombie session running forever.
        if self.other is not None and self.other.alive:
            self.other.error_reason = self.other.error_reason or (
                "Other in-memory test peer closed"
            )
            self.other.alive = False

    def close(self) -> None:
        with self._lock:
            was_alive = self.alive
            self.alive = False

        if was_alive and self.other is not None and self.other.alive:
            self.other.error_reason = self.other.error_reason or (
                "Other in-memory test peer closed"
            )
            self.other.alive = False


class DelayedPeer:
    """Latency/jitter/stall shim for the socket-free one-PC simulator.

    This is deliberately separate from the real online transport. It preserves
    packet order like TCP while allowing controlled delay, jitter and stalls.
    """

    def __init__(self, peer: InMemoryPeer, preset: NetworkTestPreset, seed: int):
        self.peer = peer
        self.preset = preset
        self.random = random.Random(seed)

        self.pending: "queue.Queue[tuple[float, dict]]" = queue.Queue(maxsize=16384)
        self._alive = True
        self._last_due = 0.0
        self._max_pending = 0
        self._last_activity = time.monotonic()

        self._thread = threading.Thread(
            target=self._pump,
            daemon=True,
            name=f"tft-v30-delay-{seed}",
        )
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
        return "simulated-link"

    @property
    def packets_in(self) -> int:
        return self.peer.packets_in

    @property
    def packets_out(self) -> int:
        return self.peer.packets_out

    @property
    def outgoing_queue_depth(self) -> int:
        return self.pending.qsize()

    @property
    def max_outgoing_queue(self) -> int:
        return max(self._max_pending, self.pending.qsize())

    @property
    def last_send_stall_ms(self) -> float:
        return 0.0

    def _schedule_time(self) -> float:
        now = time.monotonic()
        delay_ms = self.preset.one_way_ms

        if self.preset.jitter_ms:
            delay_ms += self.random.uniform(
                -self.preset.jitter_ms,
                self.preset.jitter_ms,
            )

        if (
            self.preset.stall_chance
            and self.random.random() < self.preset.stall_chance
        ):
            delay_ms += self.preset.stall_ms

        due = now + max(0.0, delay_ms) / 1000.0

        # Ordered transport: later packets do not overtake earlier packets.
        due = max(due, self._last_due + 0.000001)
        self._last_due = due
        return due

    def send(self, payload: dict) -> bool:
        if not self.alive or not isinstance(payload, dict):
            return False

        try:
            self.pending.put_nowait(
                (self._schedule_time(), dict(payload))
            )
            self._max_pending = max(
                self._max_pending,
                self.pending.qsize(),
            )
            return True
        except queue.Full:
            self.fail("v30 simulated network queue overflow")
            return False

    def _pump(self) -> None:
        held: Optional[tuple[float, dict]] = None

        while self._alive and self.peer.alive:
            if held is None:
                try:
                    held = self.pending.get(timeout=0.20)
                except queue.Empty:
                    continue

            due, payload = held
            remaining = due - time.monotonic()

            if remaining > 0:
                time.sleep(min(remaining, 0.002))
                continue

            if self._alive and self.peer.alive:
                if not self.peer.send(payload):
                    self._alive = False

            self.pending.task_done()
            held = None

            # Drain a burst of packets that became due together.
            for _ in range(63):
                if not self._alive or not self.peer.alive:
                    break

                try:
                    due2, payload2 = self.pending.get_nowait()
                except queue.Empty:
                    break

                now = time.monotonic()
                if due2 > now:
                    held = (due2, payload2)
                    break

                if not self.peer.send(payload2):
                    self._alive = False
                self.pending.task_done()

    def poll_all(self) -> list[dict]:
        return self.peer.poll_all()

    def close(self) -> None:
        self._alive = False
        self.peer.close()


class LoopbackPairJob:
    """v30 compatibility wrapper: build two in-memory peers, no sockets or TLS."""

    def __init__(self):
        self.done = threading.Event()
        self.error = ""
        self.host_peer: Optional[InMemoryPeer] = None
        self.guest_peer: Optional[InMemoryPeer] = None
        self.port = 0
        self.stage = "STARTING IN-MEMORY LINK"
        self.cancel = threading.Event()

    def start(self) -> None:
        if self.cancel.is_set():
            self.stage = "CANCELLED"
            self.done.set()
            return

        host = InMemoryPeer("host")
        guest = InMemoryPeer("guest")
        host.connect(guest)
        guest.connect(host)

        self.host_peer = host
        self.guest_peer = guest
        self.stage = "READY — IN-MEMORY LINK"
        self.done.set()

    def cancel_setup(self) -> None:
        self.cancel.set()
        if self.host_peer:
            self.host_peer.close()
        if self.guest_peer:
            self.guest_peer.close()
        self.stage = "CANCELLED"
        self.done.set()

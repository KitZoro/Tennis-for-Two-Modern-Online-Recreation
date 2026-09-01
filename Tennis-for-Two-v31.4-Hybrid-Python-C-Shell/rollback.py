from __future__ import annotations

import ast
import hashlib
import statistics
import time
from pathlib import Path
from typing import Optional

from config import (
    HANDSHAKE_TIMEOUT,
    HASH_CONFIRM_LAG,
    HASH_INTERVAL,
    INPUT_DELAY,
    MAX_ROLLBACK,
    NETWORK_INPUT_HEARTBEAT_FRAMES,
    ONLINE_INPUT_DELAY,
    PROTOCOL_VERSION,
    START_LEAD_SECONDS,
    DESYNC_NOTICE_SECONDS,
)
from diagnostics import NetDiagnostics
from game import InputState, NEUTRAL_INPUT, WorldState, initial_world, state_hash, step_world
from network import SecurePeer


def _simulation_fingerprint() -> str:
    """Fingerprint deterministic Python code while ignoring comments/formatting.

    Music and other cosmetic assets are intentionally excluded.  A gameplay or
    rollback-code difference must not be allowed to masquerade as a compatible
    online build.
    """
    root = Path(__file__).resolve().parent
    chunks: list[str] = []
    for name in ("game.py", "rollback.py", "native_core.py", "engine/tennis_core.c", "engine/tennis_core.h"):
        try:
            tree = ast.parse((root / name).read_text(encoding="utf-8"), filename=name)
            chunks.append(ast.dump(tree, annotate_fields=True, include_attributes=False))
        except (OSError, SyntaxError):
            chunks.append(f"unavailable:{name}")
    return hashlib.sha256("\n".join(chunks).encode("utf-8")).hexdigest()[:16]


SIMULATION_FINGERPRINT = _simulation_fingerprint()


class RollbackSession:
    """v28 deterministic input-sync session.

    v28 fixes:
    - synchronized frame-0 start
    - fixed 60-frame online buffer at 120 Hz
    - prediction never reads a confirmed input from a future frame
    - later speculative inputs are invalidated after a corrected prediction
    - one network packet batch causes at most one rollback
    """

    def __init__(self, local_player: int, peer: Optional[SecurePeer], is_host: bool):
        self.local_player = local_player
        self.peer = peer
        self.is_host = is_host

        self.state = initial_world()
        self.current_frame = 0

        self.inputs: dict[int, dict[int, InputState]] = {1: {}, 2: {}}
        self.predicted: dict[int, dict[int, bool]] = {1: {}, 2: {}}
        self.last_known = {1: NEUTRAL_INPUT, 2: NEUTRAL_INPUT}
        self.history: dict[int, WorldState] = {0: self.state.clone()}
        self._pending_rollback_frame: Optional[int] = None

        self.input_delay_frames = ONLINE_INPUT_DELAY if peer else INPUT_DELAY

        self.rollback_count = 0
        self.max_rollback_depth = 0
        self.correction_count = 0

        self.last_ping_sent = 0.0
        self.ping_ms = 0.0
        self.jitter_ms = 0.0
        self.ping_samples: list[float] = []
        self.pending_pings: dict[int, float] = {}
        self.next_ping_id = 1

        self.desync_warning = ""
        self.desync_warning_until = 0.0
        self.last_state_request_frame = -1

        self.started = peer is None
        self.handshake_started_at = time.monotonic()
        self.handshake_stage = "LOCAL" if peer is None else "SENDING HELLO"
        self.remote_hello = False
        self.ready_sent = False
        self.remote_ready = False
        self.start_sent = False
        self.start_ack_sent = False
        self.start_ack_received = False
        self.go_sent = False
        self.start_probe_sent_at = 0.0
        self.handshake_rtt_ms = 0.0
        self.estimated_one_way_ms = 0.0
        self.scheduled_start_at: Optional[float] = None
        self.actual_start_at: Optional[float] = None

        # Network input suppression is presentation/transport only: local input
        # is still sampled and simulated every 120 Hz tick.
        self._last_sent_input_bits: Optional[int] = None
        self._last_sent_input_frame = -10_000

        role = "host" if is_host else "guest"
        self.diagnostics = NetDiagnostics(role, local_player) if peer else None

        if self.peer:
            self.peer.send({
                "type": "hello",
                "protocol": PROTOCOL_VERSION,
                "role": role,
                "player": local_player,
                "simulation": SIMULATION_FINGERPRINT,
            })
            self.handshake_stage = "WAITING FOR PEER HELLO"

    @property
    def connection_status(self) -> str:
        if not self.peer:
            return "LOCAL"
        if not self.peer.alive:
            return "CONNECTION LOST"
        return "RUNNING" if self.started else self.handshake_stage

    def close(self) -> None:
        if self.diagnostics:
            self.diagnostics.close()

    def _reset_simulation(self, state: Optional[WorldState] = None, frame: int = 0) -> None:
        self.state = state.clone() if state is not None else initial_world()
        self.current_frame = frame
        self.inputs = {1: {}, 2: {}}
        self.predicted = {1: {}, 2: {}}
        self.last_known = {1: NEUTRAL_INPUT, 2: NEUTRAL_INPUT}
        self.history = {frame: self.state.clone()}
        self.last_state_request_frame = -1
        self._pending_rollback_frame = None

    def request_restart(self) -> None:
        if self.peer:
            self.peer.send({"type": "restart"})
        self._reset_simulation()

    def submit_local_input(self, inp: InputState) -> None:
        target_frame = self.current_frame + self.input_delay_frames
        self.inputs[self.local_player][target_frame] = inp
        self.predicted[self.local_player][target_frame] = False
        self.last_known[self.local_player] = inp

        if self.peer:
            bits = inp.packed()
            # Send a changed button state immediately.  Unchanged states are
            # already predicted by the receiver, so repeating them 120 times/s
            # only creates congestion.  A heartbeat periodically reconfirms the
            # current state without adding human-visible input latency.
            changed = bits != self._last_sent_input_bits
            heartbeat_due = (target_frame - self._last_sent_input_frame) >= NETWORK_INPUT_HEARTBEAT_FRAMES
            if changed or heartbeat_due:
                if self.peer.send({
                    "type": "input",
                    "player": self.local_player,
                    "frame": target_frame,
                    "bits": bits,
                }):
                    self._last_sent_input_bits = bits
                    self._last_sent_input_frame = target_frame

    def _confirmed_input_before(self, player: int, frame: int) -> InputState:
        best_frame = -1
        best = NEUTRAL_INPUT
        for candidate_frame, candidate in self.inputs[player].items():
            if candidate_frame >= frame:
                continue
            if self.predicted[player].get(candidate_frame, False):
                continue
            if candidate_frame > best_frame:
                best_frame = candidate_frame
                best = candidate
        return best

    def input_for(self, player: int, frame: int) -> InputState:
        known = self.inputs[player].get(frame)
        if known is not None:
            return known

        predicted = self._confirmed_input_before(player, frame)
        self.inputs[player][frame] = predicted
        self.predicted[player][frame] = True
        return predicted

    def _invalidate_predictions_after(self, player: int, frame: int) -> None:
        for future_frame in list(self.inputs[player].keys()):
            if future_frame <= frame:
                continue
            if not self.predicted[player].get(future_frame, False):
                continue
            del self.inputs[player][future_frame]
            self.predicted[player].pop(future_frame, None)

    def receive_input(self, player: int, frame: int, inp: InputState) -> None:
        if player not in (1, 2):
            return
        if frame < self.current_frame - MAX_ROLLBACK or frame > self.current_frame + 720:
            return

        old = self.inputs[player].get(frame)
        was_predicted = self.predicted[player].get(frame, False)

        self.inputs[player][frame] = inp
        self.predicted[player][frame] = False

        if was_predicted and old != inp:
            self._invalidate_predictions_after(player, frame)
            if frame < self.current_frame:
                if self._pending_rollback_frame is None:
                    self._pending_rollback_frame = frame
                else:
                    self._pending_rollback_frame = min(self._pending_rollback_frame, frame)

    def rollback(self, frame: int) -> None:
        restore = self.history.get(frame)
        if restore is None:
            return

        old_current = self.current_frame
        depth = old_current - frame
        if depth <= 0:
            return

        self.max_rollback_depth = max(self.max_rollback_depth, depth)
        self.state = restore.clone()
        self.current_frame = frame
        self.rollback_count += 1

        while self.current_frame < old_current:
            p1 = self.input_for(1, self.current_frame)
            p2 = self.input_for(2, self.current_frame)
            self.history[self.current_frame] = self.state.clone()
            step_world(self.state, p1, p2)
            self.current_frame += 1

    def apply_authoritative_state(self, frame: int, state_dict: dict) -> None:
        if self.is_host or frame < self.current_frame - MAX_ROLLBACK:
            return
        try:
            authoritative = WorldState.from_dict(state_dict)
        except (KeyError, TypeError, ValueError):
            return

        local_at_frame = self.history.get(frame)
        if local_at_frame and state_hash(local_at_frame) == state_hash(authoritative):
            return

        old_current = self.current_frame
        self.state = authoritative
        self.current_frame = frame
        self.history[frame] = authoritative.clone()
        self.correction_count += 1
        self.desync_warning = f"TRUE SYNC CORRECTION NEAR FRAME {frame}"
        self.desync_warning_until = time.monotonic() + DESYNC_NOTICE_SECONDS

        while self.current_frame < old_current:
            p1 = self.input_for(1, self.current_frame)
            p2 = self.input_for(2, self.current_frame)
            self.history[self.current_frame] = self.state.clone()
            step_world(self.state, p1, p2)
            self.current_frame += 1

    def _record_ping(self, value_ms: float) -> None:
        self.ping_ms = value_ms
        self.ping_samples.append(value_ms)
        if len(self.ping_samples) > 12:
            self.ping_samples.pop(0)
        if len(self.ping_samples) >= 2:
            diffs = [
                abs(self.ping_samples[i] - self.ping_samples[i - 1])
                for i in range(1, len(self.ping_samples))
            ]
            self.jitter_ms = statistics.fmean(diffs)

    def _handshake_fail(self, reason: str) -> None:
        if not self.peer:
            return
        self.handshake_stage = "HANDSHAKE FAILED"
        fail = getattr(self.peer, "fail", None)
        if callable(fail):
            fail(reason)
        else:
            self.peer.error_reason = reason
            self.peer.close()

    def _maybe_begin_scheduled_start(self) -> None:
        if self.started or self.scheduled_start_at is None:
            return
        if time.monotonic() < self.scheduled_start_at:
            return
        self.started = True
        self.actual_start_at = time.monotonic()
        self.handshake_stage = "RUNNING"

    def _send_ready(self) -> None:
        if not self.peer or self.ready_sent:
            return
        self.peer.send({"type": "ready", "protocol": PROTOCOL_VERSION})
        self.ready_sent = True
        self.handshake_stage = "WAITING FOR PEER READY"

    def _maybe_host_start(self) -> None:
        if not self.peer or not self.is_host or self.start_sent:
            return
        if not (self.remote_hello and self.remote_ready and self.ready_sent):
            return

        start_state = initial_world()
        self._reset_simulation(start_state, 0)
        self.input_delay_frames = ONLINE_INPUT_DELAY
        self.start_probe_sent_at = time.monotonic()
        self.peer.send({
            "type": "start",
            "protocol": PROTOCOL_VERSION,
            "frame": 0,
            "input_delay": ONLINE_INPUT_DELAY,
            "state": start_state.canonical_dict(),
        })
        self.start_sent = True
        self.handshake_stage = "WAITING FOR START ACK"

    def _handle_handshake_message(self, msg: dict) -> bool:
        if not self.peer:
            return False
        kind = msg.get("type")

        if kind == "hello":
            try:
                protocol = int(msg["protocol"])
                remote_player = int(msg["player"])
                remote_role = str(msg["role"])
                remote_simulation = str(msg["simulation"])
            except (KeyError, TypeError, ValueError):
                self._handshake_fail("Invalid HELLO packet")
                return True

            expected_player = 2 if self.local_player == 1 else 1
            expected_role = "guest" if self.is_host else "host"
            if protocol != PROTOCOL_VERSION:
                self._handshake_fail(
                    f"Protocol mismatch: local v{PROTOCOL_VERSION}, remote v{protocol}"
                )
                return True
            if remote_simulation != SIMULATION_FINGERPRINT:
                self._handshake_fail(
                    "Incompatible gameplay build: deterministic simulation differs "
                    f"(local {SIMULATION_FINGERPRINT}, remote {remote_simulation})"
                )
                return True
            if remote_player != expected_player or remote_role != expected_role:
                self._handshake_fail("Online role/player handshake mismatch")
                return True

            self.remote_hello = True
            self._send_ready()
            self._maybe_host_start()
            return True

        if kind == "ready":
            try:
                protocol = int(msg["protocol"])
            except (KeyError, TypeError, ValueError):
                self._handshake_fail("Invalid READY packet")
                return True
            if protocol != PROTOCOL_VERSION:
                self._handshake_fail(
                    f"Protocol mismatch: local v{PROTOCOL_VERSION}, remote v{protocol}"
                )
                return True
            self.remote_ready = True
            if not self.ready_sent and self.remote_hello:
                self._send_ready()
            self._maybe_host_start()
            return True

        if kind == "start":
            if self.is_host:
                self._handshake_fail("Host received an unexpected START packet")
                return True
            try:
                protocol = int(msg["protocol"])
                frame = int(msg["frame"])
                delay = int(msg["input_delay"])
                state_dict = msg["state"]
            except (KeyError, TypeError, ValueError):
                self._handshake_fail("Invalid START packet")
                return True

            if protocol != PROTOCOL_VERSION:
                self._handshake_fail(
                    f"Protocol mismatch: local v{PROTOCOL_VERSION}, remote v{protocol}"
                )
                return True
            if not isinstance(state_dict, dict) or not (0 <= delay <= 120):
                self._handshake_fail("Invalid START state or input delay")
                return True
            try:
                start_state = WorldState.from_dict(state_dict)
            except (KeyError, TypeError, ValueError):
                self._handshake_fail("Could not decode START world state")
                return True

            self._reset_simulation(start_state, frame)
            self.input_delay_frames = delay
            self.peer.send({
                "type": "start_ack",
                "protocol": PROTOCOL_VERSION,
                "frame": frame,
            })
            self.start_ack_sent = True
            self.handshake_stage = "WAITING FOR HOST GO"
            return True

        if kind == "start_ack":
            if not self.is_host or not self.start_sent:
                return True
            try:
                protocol = int(msg["protocol"])
                frame = int(msg["frame"])
            except (KeyError, TypeError, ValueError):
                self._handshake_fail("Invalid START_ACK packet")
                return True
            if protocol != PROTOCOL_VERSION or frame != self.current_frame:
                self._handshake_fail("START_ACK did not match host start state")
                return True

            self.start_ack_received = True
            if not self.go_sent:
                now = time.monotonic()
                measured_rtt = max(0.0, now - self.start_probe_sent_at)
                self.handshake_rtt_ms = measured_rtt * 1000.0
                self.estimated_one_way_ms = self.handshake_rtt_ms / 2.0

                lead_seconds = max(START_LEAD_SECONDS, measured_rtt * 1.5 + 0.25)
                self.scheduled_start_at = now + lead_seconds
                self.peer.send({
                    "type": "go",
                    "protocol": PROTOCOL_VERSION,
                    "frame": self.current_frame,
                    "lead_ms": int(round(lead_seconds * 1000.0)),
                    "estimated_one_way_ms": int(round(self.estimated_one_way_ms)),
                })
                self.go_sent = True
                self.handshake_stage = "START COUNTDOWN"
            return True

        if kind == "go":
            if self.is_host or not self.start_ack_sent:
                return True
            try:
                protocol = int(msg["protocol"])
                frame = int(msg["frame"])
                lead_ms = float(msg["lead_ms"])
                estimated_one_way_ms = float(msg["estimated_one_way_ms"])
            except (KeyError, TypeError, ValueError):
                self._handshake_fail("Invalid GO packet")
                return True
            if protocol != PROTOCOL_VERSION or frame != self.current_frame:
                self._handshake_fail("GO did not match guest start state")
                return True
            if lead_ms < 50.0 or lead_ms > 10000.0:
                self._handshake_fail("Invalid GO countdown")
                return True

            self.estimated_one_way_ms = max(0.0, estimated_one_way_ms)
            wait_ms = max(25.0, lead_ms - self.estimated_one_way_ms)
            self.scheduled_start_at = time.monotonic() + wait_ms / 1000.0
            self.handshake_stage = "START COUNTDOWN"
            return True

        if kind == "handshake_error":
            self._handshake_fail(str(msg.get("reason", "Remote handshake failed")))
            return True

        return False

    def process_network(self) -> None:
        if not self.peer:
            return

        self._pending_rollback_frame = None

        for msg in self.peer.poll_all():
            if self._handle_handshake_message(msg):
                continue

            kind = msg.get("type")

            if kind == "input":
                if not self.started:
                    continue
                try:
                    player = int(msg["player"])
                    frame = int(msg["frame"])
                    bits = int(msg["bits"])
                except (KeyError, TypeError, ValueError):
                    continue
                if player != self.local_player:
                    self.receive_input(player, frame, InputState.unpacked(bits))

            elif kind == "hash" and not self.is_host and self.started:
                try:
                    frame = int(msg["frame"])
                    remote_hash = str(msg["hash"])
                except (KeyError, TypeError, ValueError):
                    continue
                local = self.history.get(frame)
                if local and state_hash(local) != remote_hash:
                    if frame != self.last_state_request_frame:
                        self.last_state_request_frame = frame
                        self.peer.send({"type": "state_request", "frame": frame})
                        self.desync_warning = f"VERIFYING SYNC NEAR FRAME {frame}"
                        self.desync_warning_until = time.monotonic() + DESYNC_NOTICE_SECONDS

            elif kind == "state_request" and self.is_host and self.started:
                try:
                    frame = int(msg["frame"])
                except (KeyError, TypeError, ValueError):
                    continue
                authoritative = self.history.get(frame)
                if authoritative is not None:
                    self.peer.send({
                        "type": "state",
                        "frame": frame,
                        "state": authoritative.canonical_dict(),
                    })

            elif kind == "state" and not self.is_host and self.started:
                try:
                    frame = int(msg["frame"])
                    state_dict = msg["state"]
                except (KeyError, TypeError, ValueError):
                    continue
                if isinstance(state_dict, dict):
                    self.apply_authoritative_state(frame, state_dict)

            elif kind == "ping":
                try:
                    ping_id = int(msg["id"])
                except (KeyError, TypeError, ValueError):
                    continue
                self.peer.send({"type": "pong", "id": ping_id})

            elif kind == "pong":
                try:
                    ping_id = int(msg["id"])
                except (KeyError, TypeError, ValueError):
                    continue
                sent = self.pending_pings.pop(ping_id, None)
                if sent is not None:
                    self._record_ping((time.monotonic() - sent) * 1000.0)

            elif kind == "restart" and self.started:
                self._reset_simulation()

        if self._pending_rollback_frame is not None:
            frame = self._pending_rollback_frame
            self._pending_rollback_frame = None
            self.rollback(frame)

    def _maybe_ping(self) -> None:
        if not self.peer or not self.peer.alive:
            return
        now = time.monotonic()
        if now - self.last_ping_sent > 1.0:
            self.last_ping_sent = now
            ping_id = self.next_ping_id
            self.next_ping_id += 1
            self.pending_pings[ping_id] = now
            self.peer.send({"type": "ping", "id": ping_id})

    def advance(self, local_input: InputState) -> None:
        self.process_network()
        self._maybe_begin_scheduled_start()
        self._maybe_ping()

        if self.peer and not self.peer.alive:
            if self.diagnostics:
                self.diagnostics.maybe_sample(self)
            return

        if self.peer and not self.started:
            if time.monotonic() - self.handshake_started_at > HANDSHAKE_TIMEOUT:
                self._handshake_fail(
                    f"Online start handshake timed out after {int(HANDSHAKE_TIMEOUT)} seconds"
                )
            if self.diagnostics:
                self.diagnostics.maybe_sample(self)
            return

        self.submit_local_input(local_input)

        self.history[self.current_frame] = self.state.clone()
        p1 = self.input_for(1, self.current_frame)
        p2 = self.input_for(2, self.current_frame)
        step_world(self.state, p1, p2)
        self.current_frame += 1

        cutoff = self.current_frame - MAX_ROLLBACK
        for mapping in (
            self.history,
            self.inputs[1], self.inputs[2],
            self.predicted[1], self.predicted[2],
        ):
            for key in list(mapping.keys()):
                if key < cutoff:
                    del mapping[key]

        if self.peer and self.is_host and self.current_frame % HASH_INTERVAL == 0:
            hash_frame = self.current_frame - HASH_CONFIRM_LAG
            hash_state = self.history.get(hash_frame)
            if hash_state is not None:
                self.peer.send({
                    "type": "hash",
                    "frame": hash_frame,
                    "hash": state_hash(hash_state),
                })

        if self.diagnostics:
            self.diagnostics.maybe_sample(self)

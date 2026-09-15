from __future__ import annotations

import statistics
import time
from typing import Optional

from config import (
    HANDSHAKE_TIMEOUT,
    HASH_CONFIRM_LAG,
    HASH_INTERVAL,
    INPUT_DELAY,
    MAX_ROLLBACK,
    ONLINE_INPUT_DELAY,
    PROTOCOL_VERSION,
    START_LEAD_SECONDS,
    DESYNC_NOTICE_SECONDS,
)
from diagnostics import NetDiagnostics
from game import InputState, NEUTRAL_INPUT, WorldState, initial_world, state_hash, step_world
from network import SecurePeer


class RollbackSession:
    """Deterministic input-sync session with a v27 start barrier.

    Normal play sends inputs + settled-frame hashes. Full world snapshots are
    requested only after a real hash mismatch. v27 additionally makes both
    peers agree on the initial world and one fixed input delay *before* frame 0
    is allowed to advance.
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

        # v27 intentionally freezes the online buffer while reliability is
        # being tested. Both peers receive the same value in the START packet.
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

        # TLS is connected before this object exists, but simulation does not
        # begin until HELLO -> READY -> START -> START_ACK -> GO completes.
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

        role = "host" if is_host else "guest"
        self.diagnostics = NetDiagnostics(role, local_player) if peer else None

        if self.peer:
            self.peer.send({
                "type": "hello",
                "protocol": PROTOCOL_VERSION,
                "role": role,
                "player": local_player,
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
            self.peer.send({
                "type": "input",
                "player": self.local_player,
                "frame": target_frame,
                "bits": inp.packed(),
            })

    def input_for(self, player: int, frame: int) -> InputState:
        known = self.inputs[player].get(frame)
        if known is not None:
            return known
        predicted = self.last_known[player]
        self.inputs[player][frame] = predicted
        self.predicted[player][frame] = True
        return predicted

    def receive_input(self, player: int, frame: int, inp: InputState) -> None:
        if player not in (1, 2):
            return
        if frame < self.current_frame - MAX_ROLLBACK or frame > self.current_frame + 360:
            return

        old = self.inputs[player].get(frame)
        was_predicted = self.predicted[player].get(frame, False)
        self.inputs[player][frame] = inp
        self.predicted[player][frame] = False
        self.last_known[player] = inp

        if frame < self.current_frame and was_predicted and old != inp:
            self.rollback(frame)

    def rollback(self, frame: int) -> None:
        restore = self.history.get(frame)
        if restore is None:
            return

        old_current = self.current_frame
        depth = old_current - frame
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
        """Return True when the message belonged to the handshake protocol."""
        if not self.peer:
            return False

        kind = msg.get("type")
        if kind == "hello":
            try:
                protocol = int(msg["protocol"])
                remote_player = int(msg["player"])
                remote_role = str(msg["role"])
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
            if not isinstance(state_dict, dict) or not (0 <= delay <= 60):
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

                # Schedule frame 0 in the future.  The guest receives GO about
                # one one-way delay later, then subtracts that estimate from its
                # own countdown.  This prevents the host from starting ~RTT/2
                # ahead and consuming the entire rollback/input buffer.
                lead_seconds = max(
                    START_LEAD_SECONDS,
                    measured_rtt * 1.5 + 0.25,
                )
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
            # Host is authoritative, but only sends settled-frame hashes during
            # normal play. A full state travels only after a real mismatch.
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

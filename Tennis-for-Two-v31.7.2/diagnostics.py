from __future__ import annotations

import csv
import time
from datetime import datetime

from config import LOG_DIR
from game import state_hash


class NetDiagnostics:
    """Small CSV logger for real cross-internet tests.

    It intentionally logs network/game timing only: no chat text, IP addresses,
    pairing codes, or other private connection credentials.
    """

    def __init__(self, role: str, local_player: int) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = LOG_DIR / f"net_{stamp}_{role}_p{local_player}.csv"
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "seconds", "frame", "handshake_stage", "started",
            "scheduled_start_in_ms", "handshake_rtt_ms", "estimated_one_way_ms",
            "ping_ms", "jitter_ms", "input_delay_frames", "rollbacks",
            "max_rollback_depth", "corrections", "packets_in", "packets_out",
            "outgoing_queue", "max_outgoing_queue", "send_buffer_bytes",
            "last_send_stall_ms", "seconds_since_packet", "stalled",
            "termination_source", "error_reason",
            "state_frame", "state_hash",
            "p1_x", "p1_angle", "p1_power", "p1_input_bits", "p1_predicted",
            "p2_x", "p2_angle", "p2_power", "p2_input_bits", "p2_predicted",
            "ball_x", "ball_y", "ball_vx", "ball_vy", "ball_attached",
            "ball_last_hitter", "score1", "score2", "server", "rally_id",
            "hash_checks", "hash_mismatches", "first_mismatch_frame",
            "last_verified_frame", "last_local_verify_hash", "last_remote_verify_hash",
        ])
        self.started = time.monotonic()
        self.last_sample = 0.0

    def maybe_sample(self, session) -> None:
        now = time.monotonic()
        if now - self.last_sample < 1.0:
            return
        self.last_sample = now
        peer = session.peer
        scheduled = getattr(session, "scheduled_start_at", None)
        if scheduled is None or getattr(session, "started", False):
            scheduled_ms = 0.0
        else:
            scheduled_ms = max(0.0, (scheduled - now) * 1000.0)

        state = session.state
        # state is the result after current_frame-1. Inputs for that completed
        # simulation frame are the most useful pair to compare across machines.
        sample_frame = max(0, session.current_frame - 1)
        p1_in = session.inputs[1].get(sample_frame)
        p2_in = session.inputs[2].get(sample_frame)
        p1_bits = p1_in.packed() if p1_in is not None else -1
        p2_bits = p2_in.packed() if p2_in is not None else -1
        p1_pred = int(bool(session.predicted[1].get(sample_frame, False)))
        p2_pred = int(bool(session.predicted[2].get(sample_frame, False)))

        self._writer.writerow([
            f"{now - self.started:.3f}",
            session.current_frame,
            getattr(session, "connection_status", "RUNNING"),
            int(bool(getattr(session, "started", True))),
            f"{scheduled_ms:.1f}",
            f"{getattr(session, 'handshake_rtt_ms', 0.0):.1f}",
            f"{getattr(session, 'estimated_one_way_ms', 0.0):.1f}",
            f"{session.ping_ms:.1f}",
            f"{session.jitter_ms:.1f}",
            session.input_delay_frames,
            session.rollback_count,
            session.max_rollback_depth,
            session.correction_count,
            getattr(peer, "packets_in", 0) if peer else 0,
            getattr(peer, "packets_out", 0) if peer else 0,
            getattr(peer, "outgoing_queue_depth", 0) if peer else 0,
            getattr(peer, "max_outgoing_queue", 0) if peer else 0,
            getattr(peer, "send_buffer_bytes", 0) if peer else 0,
            f"{getattr(peer, 'last_send_stall_ms', 0.0):.1f}" if peer else "0",
            f"{peer.seconds_since_packet:.3f}" if peer else "0",
            int(bool(peer.stalled)) if peer else 0,
            getattr(peer, "termination_source", "") if peer else "",
            getattr(peer, "error_reason", "") if peer else "",
            state.frame,
            state_hash(state),
            f"{state.p1.x:.6f}", f"{state.p1.angle:.6f}", state.p1.power, p1_bits, p1_pred,
            f"{state.p2.x:.6f}", f"{state.p2.angle:.6f}", state.p2.power, p2_bits, p2_pred,
            f"{state.ball.x:.6f}", f"{state.ball.y:.6f}",
            f"{state.ball.vx:.6f}", f"{state.ball.vy:.6f}", int(bool(state.ball.attached)),
            state.ball.last_hitter, state.score1, state.score2, state.server, state.rally_id,
            getattr(session, "hash_checks", 0),
            getattr(session, "hash_mismatches", 0),
            getattr(session, "first_mismatch_frame", -1),
            getattr(session, "last_verified_frame", -1),
            getattr(session, "last_local_verify_hash", ""),
            getattr(session, "last_remote_verify_hash", ""),
        ])
        self._file.flush()

    def close(self) -> None:
        try:
            self._file.flush()
            self._file.close()
        except OSError:
            pass

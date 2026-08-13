from __future__ import annotations

import csv
import time
from datetime import datetime

from config import LOG_DIR


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
            "outgoing_queue", "max_outgoing_queue", "last_send_stall_ms",
            "seconds_since_packet", "stalled", "error_reason",
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
            f"{getattr(peer, 'last_send_stall_ms', 0.0):.1f}" if peer else "0",
            f"{peer.seconds_since_packet:.3f}" if peer else "0",
            int(bool(peer.stalled)) if peer else 0,
            getattr(peer, "error_reason", "") if peer else "",
        ])
        self._file.flush()

    def close(self) -> None:
        try:
            self._file.flush()
            self._file.close()
        except OSError:
            pass

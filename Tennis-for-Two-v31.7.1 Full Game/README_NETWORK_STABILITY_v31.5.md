# v31.5 Rollback + Network Stability

Built from v31.4.2 after reviewing the September 2 cross-platform guest logs.

## What the logs showed
- The compatibility-fingerprint problem was solved in the successful sessions.
- Outgoing queue depth remained tiny, so stale-input queue buildup was not the failure.
- The live transport still used two Python threads concurrently on one TLS socket: one recv thread and one send thread.
- The source tree already contained an unapplied network-stability patch designed to eliminate that exact architecture.
- The online input buffer was 30 frames (250 ms at 120 Hz), resulting in zero rollback and unnecessary input latency.

## v31.5 changes
- TLS recv and send are serialized through ONE nonblocking I/O thread.
- TCP keepalive is enabled on Linux and Windows where supported.
- A 1-second transport heartbeat continues even if the Pygame loop briefly stalls.
- Disconnect logs now include `termination_source` and `send_buffer_bytes`.
- Remote EOF is reported as `Remote closed TCP/TLS connection` instead of generic `Connection closed`.
- Online input delay reduced from 30 frames to 8 frames (66.7 ms).
- Rollback history remains 600 frames, allowing temporary spikes to be corrected.
- Protocol bumped to 31 so both players must be on this transport revision.

Both computers must use this exact build for the next online test.

# v31.6 Shared-State Verification

This is a diagnostic/playable online build based on v31.5. Transport architecture is intentionally unchanged.

## Added
- Both host and guest now record a one-second state trace: player positions, angles, power, input bits/prediction status, ball position/velocity, score, server, rally id, and deterministic state hash.
- Host sends its confirmed historical state hash once per second. Guest replies with a `hash_ack` containing the hash it had for the same frame.
- Both machines count checks and mismatches and record the first mismatch frame.
- Online overlay reports `SYNC checks/mismatches`.
- `compare_sync_logs.py HOST.csv GUEST.csv` summarizes two logs after a test.

Protocol is 32, so both computers must use this exact build.

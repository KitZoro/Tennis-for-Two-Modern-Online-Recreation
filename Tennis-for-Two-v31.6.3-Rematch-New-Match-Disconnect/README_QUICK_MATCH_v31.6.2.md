# v31.6.2 — Quick New Match

The stable v31.6 networking/sync path is preserved. This patch improves the between-match experience.

## New flow
1. Finish the online match.
2. Either player presses **R**.
3. Both computers return directly to the Online Lobby.
4. A known online opponent is automatically selected.
5. The player who wants to **host waits**.
6. The player who wants to **join presses Enter once**.

The lobby is always listening, so there is no separate Host button.

## Pairing fix
A new lobby can use a newly generated temporary TLS certificate. v31.6.2 refreshes the opponent's current pairing code before every join instead of blindly reusing a stale saved fingerprint.

Local and CPU modes are unchanged.

# v31.6.3 Match controls

Online end-of-match controls are now intentionally distinct:

- **R — REMATCH:** reset both simulations over the current connection. Host and guest roles stay the same.
- **N — NEW MATCH / SWAP HOST:** cleanly end the completed match and send both players to the quick Online Lobby. The previous opponent is preselected, so either player can host next.
- **ESC — DISCONNECT:** send an intentional session-exit message and return both players to the main menu. The remote side should not see this as a random connection failure.

The v31.5 single-thread TLS transport, v31.6 state verification, and v31.6.2 quick-lobby behavior are preserved.

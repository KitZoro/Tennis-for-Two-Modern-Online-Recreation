# v31.6.1 — Post-match disconnect restored

Online matches once again end as separate sessions. After a winner is declared, either player can press **R**. The game sends a coordinated `match_exit` message, gives the transport a short flush window, and returns both players to their menus. This makes it easy to swap who hosts the next match.

Local and CPU modes keep their existing R-to-rematch behavior.

This patch intentionally preserves the v31.6 shared-state verification and v31.5 single-I/O-thread TLS transport.

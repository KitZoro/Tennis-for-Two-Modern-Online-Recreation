# Stable Volume Fix — v31.7.0

This build fixes music or sound effects becoming softer while the game runs.

The selected gain is now applied after streamed music starts, then music and
SFX levels are locked and reapplied four times per second. This also covers
track loops, Story Mode scenes, local and CPU matches, and online play.

The existing controls are unchanged:

- **F6/F7** — music down/up by 10%
- **F8/F9** — sound effects down/up by 10%
- **M/N** — mute/unmute music or sound effects
- Range: **0% to 200%**

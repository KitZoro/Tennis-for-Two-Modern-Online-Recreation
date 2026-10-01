# v31.7.2

Based on the supplied v31.7.1 playtest-fixes copy, with its improved CPU, renderer, court boundaries, and offline timing retained.

- Define the small font in the match loop before drawing the online victory overlay.
- Handle completed-match N before the audio shortcut; preserve N as SFX mute during active play.
- Persist chapter completion and unlocks immediately after a win.
- Clear input-send suppression and desync notices when resetting simulation state.
- Tag session packets with a match generation. Ignore stale gameplay, state, handshake, and exit traffic.
- Coordinate rematches through the host and reuse the start/ack/GO countdown, including when both players request a rematch.
- Buffer same-generation inputs arriving during the start countdown.
- Honor online exit during a countdown.
- Initialize each server at 110% power for a legal opening serve; retain the existing physics and adjustable controls.
- Bump protocol to 35 so incompatible builds fail clearly.
- Route the alternate main_story.py launcher through the same main flow.
- Package one runnable version with the original music and updated launch instructions.

Validation: 16 tests pass. Real internet multiplayer and Windows runtime remain unverified.

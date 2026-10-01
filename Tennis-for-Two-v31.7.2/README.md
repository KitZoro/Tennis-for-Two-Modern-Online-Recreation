# Tennis for Two — v31.7.2

Retro tennis with local two-player matches, three computer difficulties, online play, five story chapters, and a music selector.

## Start the game

Extract the ZIP completely and open this folder.

- **Windows:** double-click `run_windows.bat`. Python 3.10 or newer is required; the launcher installs missing Python dependencies.
- **Linux:** install dependencies with `python3 -m pip install -r requirements.txt`, then run `bash run_linux.sh`.
- **Direct start:** `python3 main.py` (Windows: `py main.py`).

This is an editable Python source build, not a standalone executable. The optional native helper falls back to Python if unavailable.

## What changed

- Online victory screens render correctly.
- Either player can request a synchronized rematch. Held controls are resent, and packets from previous matches are ignored.
- After an online match, N opens the new-match flow instead of muting sound. During play, N still toggles sound effects.
- Story wins are saved before victory dialogue, so leaving that dialogue keeps earned progress.
- Each server starts at 110% power, allowing the opening shot to clear the net from the default position and angle. The receiver remains at 85%; power is still adjustable.
- Includes the previously bundled CPU, rendering, court-boundary, and low-frame-rate improvements.
- The original supplied music is included. Old notes are in `docs/history/`.

## Online compatibility

**Both players must use v31.7.2.** This build uses network protocol 35 and a new gameplay fingerprint; older builds are deliberately rejected. Connect through the Online Lobby using your existing Tailscale setup.

## Controls

| Action | Player 1 | Player 2 |
| --- | --- | --- |
| Move | A / D | Left / Right |
| Aim | W / S | Up / Down |
| Power | Q / E | Comma / Period |
| Hit | Space | Enter |

Release Hit after each point, then press again to serve.

- R after a match: rematch.
- N after an online match: new match / swap host.
- Esc / Backspace: leave the current screen or match.
- M: toggle music. N during play: toggle sound effects.
- F6 / F7: music volume. F8 / F9: sound-effect volume.
- F5: reload music. F11: fullscreen.
- Main menu 9: choose music.

## Saves

Existing story and audio settings continue to use `~/.config/tennis_for_two/`. No save migration is needed.

## Verification

Run `python3 -m unittest -v test_match_lifecycle test_playtest_fixes`.

All 16 tests passed on Linux with headless Pygame. Coverage includes online victory rendering, N-key behavior, saving story wins, default serves from both sides, stale-packet rejection, and host/guest/simultaneous rematches at simulated 0, 100 and 430 ms round-trip latency. Existing gameplay regression tests also pass.

Real internet/Tailscale play and Windows execution still need testing on the target machines. The one-PC network test uses in-memory simulated peers, not actual TCP/TLS connections.

## License

GPL-3.0; see `LICENSE`. The included music is carried over unchanged from the supplied archive.

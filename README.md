# Tennis for Two — Modern Online Recreation

A modern recreation inspired by the 1958 **Tennis for Two**, keeping the simple
ball-and-net gameplay while adding local multiplayer, CPU opponents, automatic
scoring, custom music support, fullscreen play, and long-distance online play.

## Current build

**v27.2 — synchronized online start + better disconnect diagnostics**

The v27.1 one-PC network test exposed a real start-timing bug at simulated
~430 ms RTT: the host could begin roughly one-way latency before the guest,
using up most of the input buffer before the rally even started.

v27.2 changes the online start sequence so both machines schedule frame 0 for
approximately the same future moment. It also closes a failed TLS connection
immediately and records the actual network error in the CSV log.

Both peers must use v27.2 because this build uses **protocol 28**.

## Run

Linux:

```bash
python3 main.py
```

or:

```bash
./run_linux.sh
```

Windows:

```text
py main.py
```

or double-click `run_windows.bat`.

Dependencies:

```bash
python3 -m pip install --user pygame cryptography
```

Windows:

```text
py -m pip install pygame cryptography
```

## One-PC network test

Choose **6 — NETWORK TEST — ONE PC** from the main menu.

Presets include clean local networking, 100 ms, 250 ms, and simulated ~430 ms
Argentina-style RTT, plus jitter/stall torture tests. Player 1 is local and
Player 2 is a CPU running through a second rollback session over real localhost
TLS with artificial delay.

## Network logs

Linux:

```text
~/.config/tennis_for_two/logs/
```

The v27.2 CSV includes frame counts, handshake stage, scheduled-start timing,
handshake RTT, ping, jitter, rollback depth, packet counts, send stalls, and
`error_reason`. It does not log pairing codes, IP addresses, or chat content.

## Controls

- Player 1: A/D move, W/S angle, Q/E power, Space hit
- Player 2: arrows move/angle, comma/period power, Enter hit
- F11: fullscreen
- M: music mute/unmute
- N: sound effects mute/unmute
- F5: reload music folder

## Music

Put a personal `.ogg`, `.mp3`, or `.wav` in `music/`. The `.gitignore` keeps
those files out of GitHub by default so copyrighted personal music is not
accidentally redistributed.

## License

The GitHub repository for this project uses GPL-3.0. Keep the repository's
`LICENSE` file alongside this source tree.

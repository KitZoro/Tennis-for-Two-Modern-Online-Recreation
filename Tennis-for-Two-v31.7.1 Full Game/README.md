# Tennis for Two — Modern Online Recreation

A modern recreation inspired by the 1958 **Tennis for Two**, keeping the simple
ball-and-net gameplay while adding local multiplayer, CPU opponents, automatic
scoring, custom music support, fullscreen play, and long-distance online play.

## Current build

**v31.7.1 — normalized music and calibrated 100% volume**

All three included songs are loudness-normalized to approximately **-14 LUFS**
with **-1 dB true-peak protection**, so changing songs no longer causes a large
volume jump. The built-in synth is calibrated to a similar level. Music at
100% now uses half-scale mixer gain for comfortable playback, while 200% uses
the full available gain.

### Stable live volume

The game now locks the selected music and SFX gain while it is running. Volume
is applied after music playback begins and checked four times per second, which
prevents SDL/Pygame stream starts, loops, or channel changes from gradually
softening the output.

### Live volume controls

Raise or lower audio without pausing, including during Story Mode and active
matches. Press F6/F7 for music down/up and F8/F9 for sound-effects down/up.
Each press changes the level by 10%, a popup confirms the new level, and both
settings are remembered after closing the game. Audio Settings also supports
the complete 0%-200% range.

### Main-menu BGM selector

Choose **9 — CHOOSE BGM** from the main menu. Use Up/Down to highlight the
built-in synth or any `.ogg`, `.mp3`, or `.wav` in `music/`, then press Enter
to play it. The selected track is remembered after the game closes. Press R or
F5 on the selection screen to rescan the folder.

The selector is shared by Story Mode, local play, CPU play, and online play.
All external tracks loop automatically.

### Earlier networking baseline

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
- F6/F7: music volume down/up by 10% (0%-200%)
- F8/F9: sound-effects volume down/up by 10% (0%-200%)
- Main menu 9: choose and preview BGM

## Music

Put personal `.ogg`, `.mp3`, or `.wav` files in `music/`, then choose them from
**9 — CHOOSE BGM** on the main menu. The built-in synth remains available as a
separate choice. Only redistribute tracks you created or have permission to use.

## License

The GitHub repository for this project uses GPL-3.0. Keep the repository's
`LICENSE` file alongside this source tree.

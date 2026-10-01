# Live Volume Controls — v31.6.5

Music and sound-effects volume can now be changed at any time, including while
playing Story Mode, local multiplayer, CPU matches, and online matches.

## Controls

- **F6** — lower music by 10%
- **F7** — raise music by 10%
- **F8** — lower sound effects by 10%
- **F9** — raise sound effects by 10%
- **M** — mute/unmute music
- **N** — mute/unmute sound effects

The range is **0% to 200%**. A small popup in the upper-right confirms each
change without pausing play. Music and SFX levels are saved in
`audio_settings.json` and restored the next time the game starts.

The main menu's **8 — AUDIO SETTINGS** screen controls the same saved levels.
Use Up/Down to choose Music or SFX and Left/Right to change it in 10% steps.

At 200%, loud audio files may distort or sound harsh. Lower that source if this
happens. Your operating system's master volume still controls final output.

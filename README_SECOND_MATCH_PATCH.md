# Tennis for Two v30 — Second-Match Cleanup Patch

This patch fixes a specific online-session cleanup problem in the **v30 FULL** build of *Tennis for Two*.

It is a small patch, not a new full installer or a new game version.

## What This Patch Fixes

After finishing one online match, the game could sometimes fail to start a second online match without restarting the program.

The likely cause was an old online listener or connection job remaining active after the first match.

This patch fixes that by:

- Cancelling unused host listeners after a connection is chosen
- Cancelling unused join jobs
- Waiting briefly for the old listener to release the network port
- Closing unused simultaneous-join connections
- Leaving a dead online match cleanly instead of remaining stuck in the old session

## What This Patch Does Not Change

This patch does **not** change:

- TCP/TLS networking
- Rollback logic
- Physics
- Scoring
- Player controls
- Story Mode
- Protocol 29
- The 30-frame online input buffer
- The Network Stability Patch

## Requirements

Before applying this patch, you should already have:

- **Tennis for Two v30 FULL**
- `main.py`
- `ui.py`

It is compatible with the other current v30 patches.

Put the patch file in the **same folder as `main.py`**.

Patch file:

`v30_second_match_cleanup_PATCH.py`

## Apply the Patch

### Linux

```bash
python3 v30_second_match_cleanup_PATCH.py
```

### Windows

```bat
python v30_second_match_cleanup_PATCH.py
```

After the patch finishes, launch the game normally.

Linux:

```bash
python3 main.py
```

Windows:

```bat
python main.py
```

## Important for Online Play

Both players should apply this patch before testing online together.

## Recommended Test

After applying the patch:

1. Start an online match
2. Play Game 1
3. Both players return to the menu
4. Start Game 2
5. Do **not** restart either copy of the game

The second match should be able to start normally.

## Backup

Before changing `ui.py`, the patch creates:

`ui.py.before_second_match_patch`

Keep that backup until you know the patch works correctly.

## Current Recommended v30 Setup

The current patched setup is:

- v30 FULL
- Main Story Pack
- Story + Faster Controls patch
- Network Stability patch
- Second-Match Cleanup patch

These remain patches on top of v30 rather than separate full installers.

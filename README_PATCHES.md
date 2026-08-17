# Tennis for Two v30 — Patch README

These patches are for the **v30 FULL** build of *Tennis for Two*.

They are small compatibility/fix patches, not new full installers or separate game versions.

## Requirements

Before applying the patches, make sure you already have:

- **Tennis for Two v30 FULL** installed
- `main.py`
- `config.py`
- `network.py`
- `diagnostics.py`
- `rollback.py`

For the Story + Faster Controls patch, you also need the **Main Story Pack**:

- `story.py`
- `main_story.py`

Put each patch file in the **same folder as `main.py`** before running it.

---

## Patch 1 — Story + Faster Controls

File:

`v30_story_and_faster_controls_PATCH_FIXED.py`

This patch:

- Makes the Main Story Pack menu the real main menu
- Restores Story Mode access
- Keeps the game on v30 / protocol 29
- Increases player movement speed
- Increases aiming speed
- Makes held power adjustment respond faster
- Reduces the online input buffer from 60 frames to 30 frames
- Changes Story save reset from `N` to `R` so it does not conflict with the SFX hotkey
- Creates backup copies of files before changing them

### Apply it

Linux:

```bash
python3 v30_story_and_faster_controls_PATCH_FIXED.py
```

Windows:

```bat
python v30_story_and_faster_controls_PATCH_FIXED.py
```

After applying it, launch the game normally with:

```bash
python3 main.py
```

### Important for online play

Both players should use the same gameplay settings.

Because this patch changes movement, aiming, and the online input buffer, **both computers should apply it before playing online together**.

---

## Patch 2 — Network Stability

File:

`v30_network_stability_PATCH.py`

This patch keeps the existing **TCP + TLS** networking and protocol 29, but changes how the TLS socket is handled.

The main change is:

- TLS sending and receiving are handled by **one dedicated network I/O thread** instead of separate read/write threads using the same TLS socket

It also adds clearer network diagnostics, including:

- `termination_source`
- `send_buffer_bytes`
- clearer reporting for remote disconnects, transport errors, queue overflow, and local close events

This patch does **not** change:

- Story Mode
- Player controls
- The 30-frame buffer
- Gameplay rules
- Rollback logic
- Protocol version

### Apply it

Linux:

```bash
python3 v30_network_stability_PATCH.py
```

Windows:

```bat
python v30_network_stability_PATCH.py
```

Then launch normally:

```bash
python3 main.py
```

### Important for online play

**Both computers should apply the Network Stability patch before testing online together.**

If a connection still fails, keep the new CSV logs. The added diagnostic fields are intended to help identify which side closed the connection and why.

---

## Recommended Patch Order

If you are starting from a clean v30 FULL build with the Main Story Pack:

1. Apply `v30_story_and_faster_controls_PATCH_FIXED.py`
2. Apply `v30_network_stability_PATCH.py`
3. Launch `main.py`
4. Make sure both computers have the same patches before online play

You do **not** need to reinstall v30 between these patches.

---

## Backups

The patches create backup files before changing important files.

Story + Faster Controls backups end with:

`.before_story_controls_patch`

Network Stability backups end with:

`.before_network_stability_patch`

Keep those backups until you know the patched version works correctly.

---

## If a Patch Says “PATCH NOT APPLIED”

Check that:

- The patch is in the same folder as `main.py`
- You installed **v30 FULL**
- You have the Main Story Pack before applying the Story patch
- Both computers are using protocol 29
- You are not running the patch from a different copy of the game folder

---

## Current Recommended Setup

For the current v30 build:

- v30 FULL base
- Main Story Pack
- Story + Faster Controls patch
- Network Stability patch

That is the intended patched setup. No extra installer chain is required.

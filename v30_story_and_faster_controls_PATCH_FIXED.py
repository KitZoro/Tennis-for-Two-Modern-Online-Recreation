from __future__ import annotations

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent

PATCH_NAME = "v30 Story + Faster Controls Patch"

def fail(message: str) -> None:
    print()
    print("PATCH NOT APPLIED")
    print(message)
    print()
    input("Press Enter to close...")
    raise SystemExit(1)

def backup(path: Path) -> None:
    if not path.exists():
        return
    bak = path.with_name(path.name + ".before_story_controls_patch")
    if not bak.exists():
        shutil.copy2(path, bak)

def set_assignment(text: str, name: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(name)}\s*=\s*.+$"
    if not re.search(pattern, text):
        fail(f"Could not find {name} in config.py")
    return re.sub(pattern, f"{name} = {value}", text, count=1)

# This is intentionally a PATCH, not another full installer.
# It expects:
#   1) the v30 FULL build already installed
#   2) the Main Story Pack files story.py + main_story.py present
required = [
    "main.py",
    "main_story.py",
    "story.py",
    "config.py",
    "ui.py",
    "V30_CHECK.txt",
]
missing = [name for name in required if not (ROOT / name).exists()]
if missing:
    fail(
        "This patch requires v30 FULL + the Main Story Pack.\n"
        "Missing: " + ", ".join(missing)
    )

check = (ROOT / "V30_CHECK.txt").read_text(encoding="utf-8", errors="replace")
if "TENNIS FOR TWO V30" not in check.upper():
    fail("V30_CHECK.txt does not identify this folder as the v30 FULL build.")

for name in ("main.py", "config.py", "story.py", "V30_CHECK.txt"):
    backup(ROOT / name)

# ------------------------------------------------------------
# FIX 1: make the Main Story Pack's menu the real main menu.
# ------------------------------------------------------------
story_main = (ROOT / "main_story.py").read_text(encoding="utf-8")

# Keep it identified as the existing v30 build rather than pretending this
# small compatibility patch is a whole new release/version.
story_main = story_main.replace(
    'print("Starting Tennis for Two v27.3 Story Preview")',
    'print("Starting Tennis for Two v30 FULL + Story Pack")',
)
story_main = story_main.replace(
    'pygame.display.set_caption("Tennis for Two — v27.3 Story Preview")',
    'pygame.display.set_caption("Tennis for Two — v30 FULL + Story Pack")',
)

# main_story.py already contains the correct story.main_menu/story.story_menu
# wiring. Make that the actual program entry point.
(ROOT / "main.py").write_text(story_main, encoding="utf-8")

# ------------------------------------------------------------
# FIX 2: faster-feeling controls.
# ------------------------------------------------------------
config_path = ROOT / "config.py"
config = config_path.read_text(encoding="utf-8")

# Movement/aiming are real-time speeds, so these make the controls physically
# quicker rather than merely changing FPS.
config = set_assignment(config, "PLAYER_SPEED", "340.0")
config = set_assignment(config, "ANGLE_SPEED", "120.0")

# At 120 Hz the v30 value of 10 waits ~83 ms between held power changes.
# 6 is ~50 ms.
config = set_assignment(config, "POWER_CHANGE_REPEAT", "6")

# v30's 60-frame online buffer is 500 ms at 120 Hz. 30 frames is 250 ms.
# This is the largest contributor to the "slow controls" feeling online.
config = set_assignment(config, "ONLINE_INPUT_DELAY", "30")

config_path.write_text(config, encoding="utf-8")

# ------------------------------------------------------------
# Small Story Pack compatibility fix:
# N is already used for SFX, so story-save reset uses R.
# ------------------------------------------------------------
story_path = ROOT / "story.py"
story = story_path.read_text(encoding="utf-8")
story = story.replace(
    "if event.key == pygame.K_n:",
    "if event.key == pygame.K_r:",
)
story = story.replace(
    "N RESET STORY SAVE",
    "R RESET STORY SAVE",
)
story_path.write_text(story, encoding="utf-8")

# Keep the v30 marker truthful after the patch.
(ROOT / "V30_CHECK.txt").write_text(
    "TENNIS FOR TWO v30 FULL + STORY/CONTROLS PATCH\n"
    "FPS=120\n"
    "ONLINE_INPUT_DELAY=30\n"
    "PLAYER_SPEED=340\n"
    "ANGLE_SPEED=120\n"
    "POWER_CHANGE_REPEAT=6\n"
    "STORY_MODE=ENABLED\n"
    "PROTOCOL_VERSION=29\n",
    encoding="utf-8",
)

# Syntax check the files this patch changed.
for name in ("main.py", "config.py", "story.py"):
    source = (ROOT / name).read_text(encoding="utf-8")
    compile(source, str(ROOT / name), "exec")

print()
print("============================================")
print(" v30 STORY + FASTER CONTROLS PATCH APPLIED")
print("============================================")
print("Story Mode is now on the main menu.")
print("Player movement: 285 -> 340")
print("Aim speed: 90 -> 120")
print("Held power repeat: 10 -> 6 frames")
print("Online buffer: 60 -> 30 frames")
print("v30 / Protocol 29 remain unchanged.")
print()
print("IMPORTANT: both computers need this patch for online play")
print("because movement/aiming constants must match.")
print()
print("Backups end with: .before_story_controls_patch")
print()
print("Run the game normally with:")
print("    python main.py")
print()
input("Press Enter to close...")

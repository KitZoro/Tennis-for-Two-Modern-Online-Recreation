from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui.py"
MAIN = ROOT / "main.py"
STORY = ROOT / "story.py"
BOT = ROOT / "tennis_bot_ai.py"

BOT_CODE = 'from __future__ import annotations\n\nfrom collections import deque\nimport math\nimport random\n\nfrom config import *\nfrom cpu import CpuController\nfrom game import InputState, WorldState, clamp\n\n\nclass TennisBotController(CpuController):\n    """Adaptive Tennis for Two opponent."""\n\n    VALID_STYLES = {"rally", "aggressive", "adaptive", "boss"}\n\n    def __init__(self, style: str = "adaptive"):\n        if style not in self.VALID_STYLES:\n            raise ValueError(f"Unknown TennisBot style: {style}")\n        super().__init__("hard")\n        self.style = style\n        self.player_history = deque(maxlen=180)\n        self.last_sample_frame = -999\n\n    @property\n    def display_name(self) -> str:\n        return {\n            "rally": "TENNIS BOT — RALLY",\n            "aggressive": "TENNIS BOT — AGGRESSIVE",\n            "adaptive": "TENNIS BOT — ADAPTIVE",\n            "boss": "TENNIS BOT — BOSS",\n        }[self.style]\n\n    def _remember_player(self, state: WorldState) -> None:\n        if state.frame - self.last_sample_frame >= 4:\n            self.last_sample_frame = state.frame\n            self.player_history.append((state.frame, state.p1.x))\n\n    def _predicted_player_x(self, state: WorldState) -> float:\n        if len(self.player_history) < 2:\n            return state.p1.x\n\n        old_frame, old_x = self.player_history[0]\n        new_frame, new_x = self.player_history[-1]\n        frame_span = max(1, new_frame - old_frame)\n        velocity_per_frame = (new_x - old_x) / frame_span\n        prediction = new_x + velocity_per_frame * 42.0\n        return clamp(prediction, LEFT_EDGE, NET_X - 18)\n\n    def _desired_landing_x(self, state: WorldState) -> float:\n        court_mid = (LEFT_EDGE + NET_X) / 2.0\n\n        if self.style == "rally":\n            return clamp(\n                court_mid + random.uniform(-45.0, 45.0),\n                LEFT_EDGE + 55,\n                NET_X - 70,\n            )\n\n        predicted = self._predicted_player_x(state)\n        target = NET_X - 52 if predicted < court_mid else LEFT_EDGE + 38\n\n        jitter = {\n            "aggressive": 18.0,\n            "adaptive": 10.0,\n            "boss": 5.0,\n        }.get(self.style, 10.0)\n\n        target += random.uniform(-jitter, jitter)\n        return clamp(target, LEFT_EDGE + 25, NET_X - 25)\n\n    def choose_shot(self, state: WorldState) -> None:\n        desired_x = self._desired_landing_x(state)\n\n        if self.style == "rally":\n            powers = (72, 78, 84, 90, 96, 102)\n            angles = range(116, 158, 3)\n        elif self.style == "aggressive":\n            powers = (100, 110, 120, 130, 140)\n            angles = range(104, 170, 2)\n        elif self.style == "boss":\n            powers = (95, 105, 115, 125, 135, 140)\n            angles = range(100, 172, 2)\n        else:\n            powers = (82, 90, 98, 106, 114, 122, 130)\n            angles = range(106, 168, 2)\n\n        incoming = math.hypot(state.ball.vx, state.ball.vy)\n        best_score = float("inf")\n        best_angle = 137.0\n        best_power = POWER_DEFAULT\n\n        for power in powers:\n            factor = power / 100.0\n            if state.ball.attached:\n                speed = SERVE_SPEED * factor\n            else:\n                base_speed = max(RETURN_SPEED, incoming * 1.04)\n                speed = clamp(base_speed * factor, 225.0, MAX_BALL_SPEED * 1.18)\n\n            for angle in angles:\n                landing_x, cleared = self.estimate_landing_x(\n                    state.p2.x,\n                    GROUND_Y - 12,\n                    float(angle),\n                    speed,\n                )\n                if not cleared:\n                    continue\n\n                out_penalty = 0.0\n                if landing_x < LEFT_EDGE:\n                    out_penalty += (LEFT_EDGE - landing_x) * 12.0\n                elif landing_x > NET_X - 12:\n                    out_penalty += (landing_x - (NET_X - 12)) * 12.0\n\n                target_error = abs(landing_x - desired_x)\n                player_distance = abs(\n                    landing_x - self._predicted_player_x(state)\n                )\n\n                score = target_error + out_penalty\n\n                if self.style in ("adaptive", "aggressive", "boss"):\n                    score -= player_distance * (\n                        0.27 if self.style == "boss" else 0.20\n                    )\n\n                if self.style == "aggressive":\n                    score -= power * 0.10\n                elif self.style == "boss":\n                    score -= power * 0.07\n                elif self.style == "rally":\n                    score += abs(power - 86) * 0.10\n\n                if score < best_score:\n                    best_score = score\n                    best_angle = float(angle)\n                    best_power = int(power)\n\n        self.target_angle = best_angle\n        self.target_power = best_power\n\n    def update(self, state: WorldState) -> InputState:\n        self._remember_player(state)\n        result = super().update(state)\n\n        miss_chance = {\n            "rally": 0.025,\n            "aggressive": 0.012,\n            "adaptive": 0.006,\n            "boss": 0.0,\n        }[self.style]\n\n        if result.hit and miss_chance and random.random() < miss_chance:\n            return InputState(\n                left=result.left,\n                right=result.right,\n                angle_up=result.angle_up,\n                angle_down=result.angle_down,\n                power_down=result.power_down,\n                power_up=result.power_up,\n                hit=False,\n            )\n\n        return result\n\n\nSTORY_BOT_PROFILES = {\n    "training": "rally",\n    "rival": "adaptive",\n    "assault": "aggressive",\n    "boss": "boss",\n}\n'
MARKER = "# TENNIS BOT ARENA PATCH"
OLD_RESET = '                        if cpu:\n                            cpu = CpuController(mode)\n'
NEW_RESET = '                        if cpu:\n                            cpu = TennisBotController("adaptive") if mode == "bot" else CpuController(mode)\n'

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
    bak = path.with_name(path.name + ".before_tennis_bot_patch")
    if not bak.exists():
        shutil.copy2(path, bak)

if not UI.exists() or not MAIN.exists() or not (ROOT / "cpu.py").exists():
    fail("Put this patch in the same folder as main.py, ui.py, and cpu.py.")

ui = UI.read_text(encoding="utf-8")
main = MAIN.read_text(encoding="utf-8")

if MARKER in ui:
    print()
    print("Tennis Bot Arena is already installed.")
    print()
    input("Press Enter to close...")
    raise SystemExit(0)

backup(UI)
backup(MAIN)
if STORY.exists():
    backup(STORY)
backup(BOT)

BOT.write_text(BOT_CODE, encoding="utf-8")

needle = "from cpu import CpuController"
if needle not in ui:
    fail("Could not find CpuController import in ui.py.")
ui = ui.replace(
    needle,
    needle + "\nfrom tennis_bot_ai import TennisBotController\n" + MARKER,
    1,
)

fallback_option = '        ("6", "NETWORK TEST — ONE PC", "nettest"),'
if fallback_option in ui and '"TENNIS BOT — ADAPTIVE", "bot"' not in ui:
    ui = ui.replace(
        fallback_option,
        fallback_option + '\n        ("7", "TENNIS BOT — ADAPTIVE", "bot"),',
        1,
    )

old_modes = 'if mode in ("local", "easy", "medium", "hard"):'
if old_modes not in ui:
    fail("Could not find the local/CPU mode branch in ui.py.")
ui = ui.replace(
    old_modes,
    'if mode in ("local", "easy", "medium", "hard", "bot"):',
    1,
)

old_cpu = 'cpu = CpuController(mode) if mode in ("easy", "medium", "hard") else None'
if old_cpu not in ui:
    fail("Could not find the CPU creation line in ui.py.")
ui = ui.replace(
    old_cpu,
    'cpu = TennisBotController("adaptive") if mode == "bot" else (CpuController(mode) if mode in ("easy", "medium", "hard") else None)',
    1,
)

old_label = '            "hard": "COMPUTER — HARD",\n'
if old_label not in ui:
    fail("Could not find the CPU label table in ui.py.")
ui = ui.replace(
    old_label,
    old_label + '            "bot": "TENNIS BOT — ADAPTIVE",\n',
    1,
)

if OLD_RESET not in ui:
    fail("Could not find CPU reset logic in ui.py.")
ui = ui.replace(OLD_RESET, NEW_RESET, 1)

dispatch = 'if mode in ("local", "easy", "medium", "hard"):'
if dispatch not in main:
    fail("Could not find game-mode dispatcher in main.py.")
main = main.replace(
    dispatch,
    'if mode in ("local", "easy", "medium", "hard", "bot"):',
    1,
)

story_text = None
if STORY.exists():
    story_text = STORY.read_text(encoding="utf-8")
    story_option = '        ("7", "NETWORK TEST — ONE PC", "nettest"),'
    if story_option in story_text and '"TENNIS BOT — ADAPTIVE", "bot"' not in story_text:
        story_text = story_text.replace(
            story_option,
            story_option + '\n        ("8", "TENNIS BOT — ADAPTIVE", "bot"),',
            1,
        )

UI.write_text(ui, encoding="utf-8")
MAIN.write_text(main, encoding="utf-8")
if story_text is not None:
    STORY.write_text(story_text, encoding="utf-8")

try:
    compile(BOT.read_text(encoding="utf-8"), str(BOT), "exec")
    compile(UI.read_text(encoding="utf-8"), str(UI), "exec")
    compile(MAIN.read_text(encoding="utf-8"), str(MAIN), "exec")
    if STORY.exists():
        compile(STORY.read_text(encoding="utf-8"), str(STORY), "exec")
except Exception as exc:
    for path in (UI, MAIN, STORY):
        bak = path.with_name(path.name + ".before_tennis_bot_patch")
        if bak.exists():
            shutil.copy2(bak, path)
    fail(f"Syntax check failed and backups were restored: {exc}")

print()
print("====================================")
print(" TENNIS BOT ARENA PATCH INSTALLED")
print("====================================")
print()
print("Added: TENNIS BOT — ADAPTIVE")
print()
print("The bot predicts interception, watches Player 1,")
print("aims away from predicted movement, and varies angle/power.")
print()
print("Networking and protocol 29 are untouched.")
print("Future Story profiles: rally / adaptive / aggressive / boss")
print()
print("Backups end with .before_tennis_bot_patch")
print()
input("Press Enter to close...")

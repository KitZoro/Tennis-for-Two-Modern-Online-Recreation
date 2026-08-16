from __future__ import annotations

from pathlib import Path

# Logical game canvas. ui.py scales and centers this on any monitor/window.
WIDTH, HEIGHT = 1000, 620
WINDOWED_SIZE = (1000, 620)
LETTERBOX_COLOR = (3, 6, 9)

FPS = 60
FIXED_DT = 1.0 / FPS

GROUND_Y = 438
NET_X = WIDTH // 2
NET_HEIGHT = 62
LEFT_EDGE = 115
RIGHT_EDGE = WIDTH - 115

PLAYER_SPEED = 285.0
ANGLE_SPEED = 90.0
GRAVITY = 540.0
SERVE_SPEED = 385.0
RETURN_SPEED = 445.0
MAX_BALL_SPEED = 660.0
BALL_RADIUS = 6
HIT_RANGE = 42.0
HIT_COOLDOWN_FRAMES = 12

SERVE_DELAY_SECONDS = 0.25
SERVE_DELAY_FRAMES = max(1, round(FPS * SERVE_DELAY_SECONDS))

POWER_MIN = 40
POWER_MAX = 140
POWER_STEP = 5
POWER_DEFAULT = 85
POWER_CHANGE_REPEAT = 5

WIN_SCORE = 7
WIN_BY = 2

# Rollback/networking.
# v25 no longer pushes full world snapshots on a timer. The host sends hashes
# of settled frames; a full state is sent only when the guest detects a mismatch.
INPUT_DELAY = 10
# v27 keeps one fixed, agreed online buffer while we stabilize netplay.
# 16 frames = ~267 ms at 60 Hz: intentionally conservative for the
# Alabama <-> Argentina test path without the two peers changing delay
# independently during a rally.
ONLINE_INPUT_DELAY = 16
MIN_INPUT_DELAY = 8
MAX_INPUT_DELAY = 24
INPUT_DELAY_ADJUST_SECONDS = 2.0
PROTOCOL_VERSION = 28
# Protocol 28 intentionally prevents v27.1 and v27.2 peers from mixing; the start handshake changed.
HANDSHAKE_TIMEOUT = 20.0
# Host schedules frame 0 in the near future so both peers start together.
START_LEAD_SECONDS = 1.25
OUTGOING_QUEUE_MAX = 2048

MAX_ROLLBACK = 300
HASH_INTERVAL = 60
HASH_CONFIRM_LAG = 100
DESYNC_NOTICE_SECONDS = 2.5

MAX_PACKET_SIZE = 16_384
MAX_PACKETS_PER_SECOND = 180
CONNECT_TIMEOUT = 30.0
NETWORK_STALL_WARNING = 5.0
NETWORK_DEAD_TIMEOUT = 30.0

DEFAULT_ONLINE_PORT = 50007
PAIR_DISCOVERY_PORT = 50008
PAIR_DISCOVERY_TIMEOUT = 1.25
TAILSCALE_REFRESH_SECONDS = 2.0

# Visual smoothing is presentation only; collisions use the deterministic state.
RENDER_SMOOTHING = 0.34
RENDER_SNAP_DISTANCE = 150.0
RENDER_BALL_SNAP_DISTANCE = 210.0

# Audio.
AUDIO_SAMPLE_RATE = 44_100
AUDIO_VOLUME = 0.45
MUSIC_VOLUME = 0.16

# Theme.
BG = (15, 21, 28)
GRID = (61, 111, 76)
GRID_BRIGHT = (88, 142, 99)
GREEN = (79, 255, 117)
WHITE = (232, 255, 237)
MUTED = (134, 176, 144)
DARK_PANEL = (24, 35, 43)
ERROR = (255, 120, 120)

CONFIG_DIR = Path.home() / ".config" / "tennis_for_two"
TRUST_FILE = CONFIG_DIR / "trusted_hosts.json"
LOG_DIR = CONFIG_DIR / "logs"

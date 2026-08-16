from __future__ import annotations

import math
import time
from typing import Optional

import pygame

from audio import SoundManager
from config import *
from cpu import CpuController
from game import (
    InputState, PlayerState, RenderState, initial_world, step_world,
)
from network import (
    SecurePeer, ConnectJob, PairingDiscovery, TailscalePeerInfo,
    clipboard_get, clipboard_set, format_security_code, normalize_security_code,
    save_trusted_peer, tailscale_snapshot, trusted_code_for_peer,
)
from rollback import RollbackSession
from network_test import NETWORK_TEST_PRESETS, DelayedPeer, LoopbackPairJob, NetworkTestPreset

DISPLAY = None
FULLSCREEN = False
SOUND: Optional[SoundManager] = None


def _open_display(fullscreen: bool):
    """Create the real OS window. Gameplay is always drawn to 1000x620."""
    global DISPLAY, FULLSCREEN
    FULLSCREEN = bool(fullscreen)

    if FULLSCREEN:
        DISPLAY = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        DISPLAY = pygame.display.set_mode(
            WINDOWED_SIZE,
            pygame.RESIZABLE,
        )
    return DISPLAY


def toggle_fullscreen() -> None:
    """F11 switches between a resizable window and borderless display fullscreen."""
    _open_display(not FULLSCREEN)


def _display_transform() -> tuple[float, int, int, int, int]:
    """Return scale, offset x/y, and scaled logical width/height."""
    if DISPLAY is None:
        return 1.0, 0, 0, WIDTH, HEIGHT

    dw, dh = DISPLAY.get_size()
    if dw <= 0 or dh <= 0:
        return 1.0, 0, 0, WIDTH, HEIGHT

    scale = min(dw / WIDTH, dh / HEIGHT)
    scaled_w = max(1, int(round(WIDTH * scale)))
    scaled_h = max(1, int(round(HEIGHT * scale)))
    offset_x = (dw - scaled_w) // 2
    offset_y = (dh - scaled_h) // 2
    return scale, offset_x, offset_y, scaled_w, scaled_h


def present(logical_screen: pygame.Surface) -> None:
    """Scale and center the entire game while preserving its aspect ratio."""
    if DISPLAY is None:
        return

    scale, offset_x, offset_y, scaled_w, scaled_h = _display_transform()

    DISPLAY.fill(LETTERBOX_COLOR)

    if scaled_w == WIDTH and scaled_h == HEIGHT:
        scaled = logical_screen
    else:
        # Normal scale keeps the oscilloscope-style lines crisp.
        scaled = pygame.transform.scale(logical_screen, (scaled_w, scaled_h))

    DISPLAY.blit(scaled, (offset_x, offset_y))
    pygame.display.flip()


def display_to_game_pos(pos: tuple[int, int]) -> tuple[int, int]:
    """Convert a real window/fullscreen mouse position into logical game coordinates."""
    scale, offset_x, offset_y, _, _ = _display_transform()
    if scale <= 0:
        return pos
    x = int((pos[0] - offset_x) / scale)
    y = int((pos[1] - offset_y) / scale)
    return x, y


def game_events():
    """Yield game events while handling display-only controls centrally."""
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            toggle_fullscreen()
            continue

        if event.type == pygame.MOUSEBUTTONDOWN and hasattr(event, "pos"):
            mapped = display_to_game_pos(event.pos)
            event = pygame.event.Event(
                event.type,
                {**event.dict, "pos": mapped},
            )

        yield event


def handle_audio_hotkey(event) -> bool:
    """Return True when an audio-only hotkey consumed this key event."""
    if event.type != pygame.KEYDOWN or SOUND is None:
        return False

    if event.key == pygame.K_m:
        SOUND.toggle_music()
        return True
    if event.key == pygame.K_n:
        SOUND.toggle_sfx()
        return True
    if event.key == pygame.K_F5:
        SOUND.reload_music()
        return True
    return False


def glow_line(surface, color, start, end, width=2):
    for extra, alpha in ((11, 20), (7, 35), (4, 65)):
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(layer, (*color, alpha), start, end, width + extra)
        surface.blit(layer, (0, 0))
    pygame.draw.line(surface, color, start, end, width)


def glow_circle(surface, color, center, radius):
    for extra, alpha in ((14, 20), (9, 40), (5, 75)):
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(layer, (*color, alpha), center, radius + extra)
        surface.blit(layer, (0, 0))
    pygame.draw.circle(surface, color, center, radius)


def draw_grid(screen):
    for x in range(15, WIDTH, 40):
        pygame.draw.line(screen, GRID_BRIGHT if x % 80 == 15 else GRID, (x, 8), (x, HEIGHT - 8), 1)
    for y in range(10, HEIGHT, 49):
        pygame.draw.line(screen, GRID_BRIGHT if y % 98 == 10 else GRID, (10, y), (WIDTH - 10, y), 1)


def draw_text(screen, font, text, pos, color=WHITE, center=False):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    screen.blit(surf, rect)


def draw_player(screen, player: PlayerState):
    px = int(player.x)
    glow_line(screen, GREEN, (px, GROUND_Y - 17), (px, GROUND_Y + 2), 3)
    rad = math.radians(player.angle)
    end = (
        int(player.x + math.cos(rad) * 46),
        int(GROUND_Y - math.sin(rad) * 46),
    )
    glow_line(screen, WHITE, (px, GROUND_Y - 4), end, 2)



def draw_keycap(screen, font, label: str, x: int, y: int, width: int = 30) -> int:
    """Draw a small keyboard-key style control hint and return its right edge."""
    height = 25
    rect = pygame.Rect(x, y, width, height)

    # Soft shadow/glow so the key is noticeable without becoming distracting.
    shadow = pygame.Surface((width + 8, height + 8), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 80), (4, 4, width, height), border_radius=6)
    screen.blit(shadow, (x - 4, y - 4))

    pygame.draw.rect(screen, (36, 53, 61), rect, border_radius=5)
    pygame.draw.rect(screen, (96, 148, 112), rect, 1, border_radius=5)
    draw_text(screen, font, label, rect.center, WHITE, center=True)
    return rect.right


def draw_player_controls(screen, font, player: int) -> None:
    """Two-row control card that always fits on either side."""
    panel_w = 330
    panel_h = 78
    y = 454
    x = 24 if player == 1 else WIDTH - 24 - panel_w

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (18, 28, 35, 205), (0, 0, panel_w, panel_h), border_radius=9)
    pygame.draw.rect(panel, (*GREEN, 105), (0, 0, panel_w, panel_h), 1, border_radius=9)
    screen.blit(panel, (x, y))

    title = "PLAYER 1" if player == 1 else "PLAYER 2"
    draw_text(screen, font, title, (x + 10, y + 5), GREEN)

    def key(label: str, px: int, py: int, width: int = 28) -> int:
        return draw_keycap(screen, font, label, px, py, width) + 4

    row1_y = y + 28
    row2_y = y + 52

    # Row 1: movement + angle.
    cursor = x + 10
    if player == 1:
        cursor = key("A", cursor, row1_y)
        cursor = key("D", cursor, row1_y)
    else:
        cursor = key("←", cursor, row1_y)
        cursor = key("→", cursor, row1_y)
    draw_text(screen, font, "MOVE", (cursor, row1_y + 5), MUTED)
    cursor += 52

    if player == 1:
        cursor = key("W", cursor, row1_y)
        cursor = key("S", cursor, row1_y)
    else:
        cursor = key("↑", cursor, row1_y)
        cursor = key("↓", cursor, row1_y)
    draw_text(screen, font, "ANGLE", (cursor, row1_y + 5), MUTED)

    # Row 2: power + hit.
    cursor = x + 10
    if player == 1:
        cursor = key("Q", cursor, row2_y)
        cursor = key("E", cursor, row2_y)
    else:
        cursor = key(",", cursor, row2_y)
        cursor = key(".", cursor, row2_y)
    draw_text(screen, font, "POWER", (cursor, row2_y + 5), MUTED)
    cursor += 62

    if player == 1:
        cursor = key("SPACE", cursor, row2_y, 58)
    else:
        cursor = key("ENTER", cursor, row2_y, 58)
    draw_text(screen, font, "HIT", (cursor, row2_y + 5), MUTED)



def draw_game(screen, session: RollbackSession, fonts, mode_label: str, render_state: Optional[RenderState] = None):
    large, medium, small = fonts
    state = session.state

    screen.fill(BG)
    draw_grid(screen)
    pygame.draw.rect(screen, (31, 43, 50), (8, 8, WIDTH - 16, HEIGHT - 16), 8, border_radius=34)
    pygame.draw.rect(screen, (49, 70, 62), (13, 13, WIDTH - 26, HEIGHT - 26), 2, border_radius=30)

    glow_line(screen, GREEN, (135, GROUND_Y), (WIDTH - 135, GROUND_Y), 3)
    glow_line(screen, GREEN, (NET_X, GROUND_Y), (NET_X, GROUND_Y - NET_HEIGHT), 3)

    if render_state is None:
        draw_player(screen, state.p1)
        draw_player(screen, state.p2)
        ball_draw_x, ball_draw_y = state.ball.x, state.ball.y
    else:
        p1_draw = PlayerState(
            x=render_state.p1_x,
            angle=state.p1.angle,
            cooldown_frames=state.p1.cooldown_frames,
            power=state.p1.power,
            power_repeat_frames=state.p1.power_repeat_frames,
        )
        p2_draw = PlayerState(
            x=render_state.p2_x,
            angle=state.p2.angle,
            cooldown_frames=state.p2.cooldown_frames,
            power=state.p2.power,
            power_repeat_frames=state.p2.power_repeat_frames,
        )
        draw_player(screen, p1_draw)
        draw_player(screen, p2_draw)
        ball_draw_x, ball_draw_y = render_state.ball_x, render_state.ball_y

    glow_circle(screen, WHITE, (int(ball_draw_x), int(ball_draw_y)), BALL_RADIUS)

    draw_text(screen, large, f"{state.score1}  {state.score2}", (WIDTH - 93, 64), WHITE, center=True)
    draw_text(screen, medium, state.message, (WIDTH // 2, 60), GREEN, center=True)
    draw_text(screen, small, f"P1 {state.p1.angle:05.1f}°  POWER {state.p1.power:3d}%", (34, 32))
    draw_text(screen, small, f"P2 {state.p2.angle:05.1f}°  POWER {state.p2.power:3d}%", (34, 60))

    gauge_x, gauge_w, gauge_h = 34, 180, 8
    for index, player in enumerate((state.p1, state.p2)):
        gauge_y = 84 + index * 18
        pygame.draw.rect(screen, DARK_PANEL, (gauge_x, gauge_y, gauge_w, gauge_h), border_radius=3)
        fraction = (player.power - POWER_MIN) / (POWER_MAX - POWER_MIN)
        fill_w = int(gauge_w * fraction)
        gauge_color = GREEN if 70 <= player.power <= 110 else (255, 214, 90)
        pygame.draw.rect(screen, gauge_color, (gauge_x, gauge_y, fill_w, gauge_h), border_radius=3)
        normal_x = gauge_x + int(gauge_w * ((100 - POWER_MIN) / (POWER_MAX - POWER_MIN)))
        pygame.draw.line(screen, WHITE, (normal_x, gauge_y - 2), (normal_x, gauge_y + gauge_h + 2), 1)

    # Always-visible controls: one compact strip on each player's side.
    draw_player_controls(screen, small, 1)
    draw_player_controls(screen, small, 2)

    draw_text(screen, small, mode_label, (WIDTH // 2, HEIGHT - 24), MUTED, center=True)
    draw_text(
        screen, small,
        f"PING {session.ping_ms:4.0f} ms  JIT {session.jitter_ms:3.0f}  "
        f"RB {session.rollback_count}/{session.max_rollback_depth}  "
        f"CORR {session.correction_count}  BUF {session.input_delay_frames}f",
        (WIDTH // 2, HEIGHT - 48), MUTED, center=True
    )
    if session.desync_warning and time.monotonic() < session.desync_warning_until:
        draw_text(screen, small, session.desync_warning, (WIDTH // 2, 96), ERROR, center=True)

    if session.peer and session.peer.alive and not session.started:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 125))
        screen.blit(overlay, (0, 0))
        draw_text(screen, medium, "SECURE MATCH SYNCING", (WIDTH // 2, HEIGHT // 2 - 18), GREEN, center=True)
        draw_text(screen, small, session.connection_status, (WIDTH // 2, HEIGHT // 2 + 20), WHITE, center=True)
        draw_text(screen, small, "Gameplay starts only after both computers are ready", (WIDTH // 2, HEIGHT // 2 + 48), MUTED, center=True)

    if session.peer and session.peer.stalled:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 105))
        screen.blit(overlay, (0, 0))
        remaining = max(0, int(NETWORK_DEAD_TIMEOUT - session.peer.seconds_since_packet))
        draw_text(screen, medium, "CONNECTION DELAYED — WAITING", (WIDTH // 2, HEIGHT // 2 - 14), (255, 214, 90), center=True)
        draw_text(screen, small, f"Will keep trying for {remaining} more seconds", (WIDTH // 2, HEIGHT // 2 + 22), WHITE, center=True)

    if session.peer and not session.peer.alive:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        draw_text(screen, medium, "SECURE CONNECTION LOST", (WIDTH // 2, HEIGHT // 2 - 14), ERROR, center=True)
        reason = session.peer.error_reason or "The other computer stopped responding"
        draw_text(screen, small, reason[:80], (WIDTH // 2, HEIGHT // 2 + 22), WHITE, center=True)


def keyboard_input_for(player: int) -> InputState:
    keys = pygame.key.get_pressed()
    if player == 1:
        return InputState(
            left=keys[pygame.K_a],
            right=keys[pygame.K_d],
            angle_up=keys[pygame.K_w],
            angle_down=keys[pygame.K_s],
            power_down=keys[pygame.K_q],
            power_up=keys[pygame.K_e],
            hit=keys[pygame.K_SPACE],
        )
    return InputState(
        left=keys[pygame.K_LEFT],
        right=keys[pygame.K_RIGHT],
        angle_up=keys[pygame.K_UP],
        angle_down=keys[pygame.K_DOWN],
        power_down=keys[pygame.K_COMMA],
        power_up=keys[pygame.K_PERIOD],
        hit=keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER],
    )


def menu(screen, fonts) -> Optional[str]:
    large, medium, small = fonts
    options = [
        ("1", "LOCAL TWO PLAYER", "local"),
        ("2", "COMPUTER — EASY", "easy"),
        ("3", "COMPUTER — MEDIUM", "medium"),
        ("4", "COMPUTER — HARD", "hard"),
        ("5", "ONLINE LOBBY — TAILSCALE", "online"),
        ("6", "NETWORK TEST — ONE PC", "nettest"),
    ]
    clock = pygame.time.Clock()
    while True:
        clock.tick(FPS)
        for event in game_events():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if handle_audio_hotkey(event):
                    continue
                for key, _, mode in options:
                    if event.unicode == key:
                        return mode

        screen.fill(BG)
        draw_grid(screen)
        draw_text(screen, large, "TENNIS FOR TWO", (WIDTH // 2, 72), GREEN, center=True)
        draw_text(screen, small, "CPU + TLS 1.3 + ROLLBACK + AUTO-PAIR + CUSTOM MUSIC", (WIDTH // 2, 108), MUTED, center=True)
        y = 143
        for key, label, _ in options:
            pygame.draw.rect(screen, DARK_PANEL, (230, y - 21, 540, 42), border_radius=9)
            draw_text(screen, medium, f"{key}  {label}", (WIDTH // 2, y), WHITE, center=True)
            y += 50
        if SOUND is not None:
            music_state = "OFF" if SOUND.music_muted else "ON"
            sfx_state = "OFF" if SOUND.sfx_muted else "ON"
            draw_text(
                screen, small,
                f"MUSIC {music_state}: {SOUND.music_name}    SFX {sfx_state}",
                (WIDTH // 2, 510), MUTED, center=True
            )
        draw_text(screen, small, "F11 FULLSCREEN   M MUSIC   N SFX   F5 RELOAD MUSIC   ESC QUITS", (WIDTH // 2, 548), MUTED, center=True)
        present(screen)



def network_test_menu(screen, fonts) -> Optional[NetworkTestPreset]:
    """Choose a one-PC latency profile. No Tailscale or second computer needed."""
    _, medium, small = fonts
    clock = pygame.time.Clock()
    while True:
        clock.tick(FPS)
        for event in game_events():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    return None
                if handle_audio_hotkey(event):
                    continue
                for preset in NETWORK_TEST_PRESETS:
                    if event.unicode == preset.key:
                        return preset

        screen.fill(BG)
        draw_grid(screen)
        draw_text(screen, medium, "NETWORK TEST — ONE PC", (WIDTH // 2, 58), GREEN, center=True)
        draw_text(
            screen,
            small,
            "P1 = YOU • P2 = REMOTE CPU • REAL LOCAL TLS + ARTIFICIAL INTERNET DELAY",
            (WIDTH // 2, 91),
            MUTED,
            center=True,
        )

        y = 140
        for preset in NETWORK_TEST_PRESETS:
            pygame.draw.rect(screen, DARK_PANEL, (180, y - 19, 640, 40), border_radius=9)
            draw_text(screen, small, f"{preset.key}  {preset.label}", (235, y - 8), WHITE)
            draw_text(screen, small, preset.description, (515, y - 8), MUTED, center=False)
            y += 57

        draw_text(
            screen,
            small,
            "This delays both directions but keeps packets ordered like TCP.",
            (WIDTH // 2, 507),
            WHITE,
            center=True,
        )
        draw_text(
            screen,
            small,
            "Use 4 first for the Argentina-style test. ESC returns.",
            (WIDTH // 2, 538),
            MUTED,
            center=True,
        )
        present(screen)


def _wait_for_loopback_test_pair(screen, fonts, preset: NetworkTestPreset):
    """Create the localhost TLS pair while keeping the Pygame window responsive."""
    _, medium, small = fonts
    job = LoopbackPairJob()
    job.start()
    clock = pygame.time.Clock()

    while not job.done.is_set():
        clock.tick(FPS)
        for event in game_events():
            if event.type == pygame.QUIT:
                job.cancel_setup()
                return None
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                job.cancel_setup()
                return None
            if event.type == pygame.KEYDOWN:
                handle_audio_hotkey(event)

        screen.fill(BG)
        draw_grid(screen)
        draw_text(screen, medium, "BUILDING LOCAL NETWORK TEST", (WIDTH // 2, 235), GREEN, center=True)
        draw_text(screen, small, preset.label, (WIDTH // 2, 282), WHITE, center=True)
        draw_text(screen, small, job.stage, (WIDTH // 2, 320), MUTED, center=True)
        draw_text(screen, small, "Creating two TLS endpoints on this PC...", (WIDTH // 2, 362), MUTED, center=True)
        present(screen)

    if job.error or job.host_peer is None or job.guest_peer is None:
        until = time.monotonic() + 4.0
        while time.monotonic() < until:
            for event in game_events():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    return None
            screen.fill(BG)
            draw_grid(screen)
            draw_text(screen, medium, "NETWORK TEST SETUP FAILED", (WIDTH // 2, 250), ERROR, center=True)
            draw_text(screen, small, (job.error or "Unknown error")[:110], (WIDTH // 2, 305), WHITE, center=True)
            draw_text(screen, small, "PRESS ANY KEY TO RETURN", (WIDTH // 2, 350), MUTED, center=True)
            present(screen)
        return None

    return job.host_peer, job.guest_peer


def run_network_test(screen, fonts, preset: NetworkTestPreset) -> None:
    """Run both online peers inside one process; the remote peer is CPU-driven."""
    pair = _wait_for_loopback_test_pair(screen, fonts, preset)
    if pair is None:
        return

    raw_host, raw_guest = pair
    host_peer = DelayedPeer(raw_host, preset, seed=27101)
    guest_peer = DelayedPeer(raw_guest, preset, seed=27102)
    host_session = RollbackSession(1, host_peer, is_host=True)
    guest_session = RollbackSession(2, guest_peer, is_host=False)
    remote_cpu = CpuController("medium")
    render_state = RenderState.from_world(host_session.state)

    clock = pygame.time.Clock()
    accumulator = 0.0
    running = True
    mode_label = f"NETWORK TEST — {preset.label} — REMOTE CPU"

    try:
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            for event in game_events():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        running = False
                    elif handle_audio_hotkey(event):
                        pass
                    elif event.key == pygame.K_r and host_session.state.winner:
                        # Host sends the real restart packet to the simulated remote.
                        host_session.request_restart()
                        remote_cpu = CpuController("medium")
                        render_state = RenderState.from_world(host_session.state)

            accumulator += dt
            while accumulator >= FIXED_DT:
                before = host_session.state.clone()
                p1 = keyboard_input_for(1)
                p2 = remote_cpu.update(guest_session.state)

                # These are two independent rollback sessions connected through
                # actual localhost TLS. Only the transport timing is artificial.
                host_session.advance(p1)
                guest_session.advance(p2)

                if SOUND is not None:
                    SOUND.observe(before, host_session.state)
                render_state.update(host_session.state, 1)
                accumulator -= FIXED_DT

            draw_game(screen, host_session, fonts, mode_label, render_state)
            _, _, small = fonts
            draw_text(
                screen,
                small,
                f"SIM TARGET {preset.description}   REMOTE FRAME {guest_session.current_frame}   "
                f"REMOTE RB {guest_session.rollback_count}/{guest_session.max_rollback_depth}",
                (WIDTH // 2, 122),
                MUTED,
                center=True,
            )
            present(screen)
    finally:
        host_session.close()
        guest_session.close()
        host_peer.close()
        guest_peer.close()

def text_entry(screen, fonts, prompt: str, initial: str = "", code_mode: bool = False) -> Optional[str]:
    _, medium, small = fonts
    value = initial
    clock = pygame.time.Clock()
    paste_status = ""
    paste_status_until = 0.0
    input_box = pygame.Rect(180, 275, 640, 58)

    def paste_from_clipboard() -> None:
        nonlocal value, paste_status, paste_status_until
        pasted, method = clipboard_get()
        if pasted:
            value = format_security_code(pasted) if code_mode else pasted.strip()
            paste_status = f"PASTED USING {method}"
        else:
            paste_status = "NOTHING FOUND IN CLIPBOARD"
        paste_status_until = time.monotonic() + 3.0

    while True:
        clock.tick(FPS)
        for event in game_events():
            if event.type == pygame.QUIT:
                return None

            if event.type == pygame.MOUSEBUTTONDOWN:
                # Right-click and middle-click both paste. Clicking the box with
                # either button behaves like a normal Linux paste operation.
                if event.button in (2, 3) and input_box.collidepoint(event.pos):
                    paste_from_clipboard()

            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_RETURN:
                    return format_security_code(value) if code_mode else value.strip()
                if event.key == pygame.K_BACKSPACE:
                    value = value[:-1]
                elif (
                    event.key == pygame.K_v and (mods & pygame.KMOD_CTRL)
                ) or (
                    event.key == pygame.K_INSERT and (mods & pygame.KMOD_SHIFT)
                ):
                    paste_from_clipboard()
                elif event.unicode and event.unicode.isprintable():
                    value += event.unicode
                    if code_mode:
                        value = format_security_code(value)

        screen.fill(BG)
        draw_grid(screen)
        draw_text(screen, medium, prompt, (WIDTH // 2, 225), WHITE, center=True)
        pygame.draw.rect(screen, DARK_PANEL, input_box, border_radius=8)
        draw_text(screen, medium, value + "_", (WIDTH // 2, 304), GREEN, center=True)

        help_text = "CTRL+V / SHIFT+INSERT / RIGHT-CLICK / MIDDLE-CLICK TO PASTE"
        draw_text(screen, small, help_text, (WIDTH // 2, 375), MUTED, center=True)

        if time.monotonic() < paste_status_until:
            status_color = GREEN if paste_status.startswith("PASTED") else ERROR
            draw_text(screen, small, paste_status, (WIDTH // 2, 407), status_color, center=True)

        draw_text(screen, small, "ENTER CONFIRMS — ESC CANCELS", (WIDTH // 2, 438), MUTED, center=True)
        present(screen)


def wait_for_connection(screen, fonts, job: ConnectJob, host_mode: bool) -> Optional[SecurePeer]:
    _, medium, small = fonts
    clock = pygame.time.Clock()
    copied_until = 0.0
    copy_status = "PRESS C TO COPY FOR DISCORD"
    while not job.done.is_set():
        clock.tick(FPS)
        for event in game_events():
            if event.type == pygame.QUIT:
                job.cancel.set()
                return None
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    job.cancel.set()
                    return None
                if host_mode and event.key == pygame.K_c and job.result.fingerprint:
                    copied, method = clipboard_set(job.result.fingerprint)
                    if copied:
                        copy_status = f"COPIED USING {method}"
                        copied_until = time.monotonic() + 3.0
                    else:
                        copy_status = "NOT COPIED FOR DISCORD — INSTALL XCLIP"
                        copied_until = time.monotonic() + 5.0

        screen.fill(BG)
        draw_grid(screen)
        if host_mode:
            draw_text(screen, medium, "WAITING FOR SECURE PLAYER", (WIDTH // 2, 225), WHITE, center=True)
            if job.result.fingerprint:
                draw_text(screen, small, "SHORT PAIRING CODE:", (WIDTH // 2, 275), MUTED, center=True)
                draw_text(screen, medium, job.result.fingerprint, (WIDTH // 2, 320), GREEN, center=True)
                status = copy_status if time.monotonic() < copied_until else "PRESS C TO COPY FOR DISCORD"
                status_color = GREEN if status.startswith("COPIED") else (
                    ERROR if status.startswith("NOT COPIED") else MUTED
                )
                draw_text(screen, small, status, (WIDTH // 2, 360), status_color, center=True)
        else:
            draw_text(screen, medium, "ESTABLISHING TLS 1.3 CONNECTION", (WIDTH // 2, 285), WHITE, center=True)

        draw_text(screen, small, "ESC OR BACKSPACE CANCELS", (WIDTH // 2, 415), MUTED, center=True)
        present(screen)

    if job.result.error:
        start = time.monotonic()
        while time.monotonic() - start < 3.0:
            for event in game_events():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    return None
            screen.fill(BG)
            draw_grid(screen)
            draw_text(screen, medium, "CONNECTION FAILED", (WIDTH // 2, 260), ERROR, center=True)
            draw_text(screen, small, job.result.error[:110], (WIDTH // 2, 315), WHITE, center=True)
            draw_text(screen, small, "PRESS ANY KEY OR WAIT TO RETURN", (WIDTH // 2, 365), MUTED, center=True)
            present(screen)
        return None

    return job.result.peer



def online_lobby(screen, fonts) -> Optional[tuple[str, SecurePeer, int]]:
    """One Tailscale screen that can receive a connection or join a visible peer.

    v27 keeps the listener alive while an outgoing connection is attempted. If
    both players press JOIN at nearly the same time, both TCP paths may exist for
    a moment; a deterministic Tailscale-IP tie-break makes both computers keep
    opposite ends of the *same* connection instead of cancelling both listeners.
    """
    _, medium, small = fonts
    clock = pygame.time.Clock()
    port = DEFAULT_ONLINE_PORT

    host_job = ConnectJob()
    host_job.start_host(port)

    pairing_discovery = PairingDiscovery(lambda: host_job.result.fingerprint)

    peers: list[TailscalePeerInfo] = []
    self_name = ""
    tailscale_status = "CHECKING TAILSCALE..."
    last_refresh = -999.0
    selected_index: Optional[int] = None
    code_value = ""
    status_message = "OPEN v27+ ONLINE LOBBY ON BOTH COMPUTERS"
    status_color = MUTED
    copy_status_until = 0.0
    joining_job: Optional[ConnectJob] = None
    joining_peer: Optional[TailscalePeerInfo] = None

    def refresh() -> None:
        nonlocal self_name, peers, tailscale_status, last_refresh, selected_index
        self_name, peers, tailscale_status = tailscale_snapshot()
        last_refresh = time.monotonic()
        if selected_index is not None and selected_index >= len(peers):
            selected_index = None

    def ip_key(address: str) -> tuple[int, int, int, int]:
        try:
            parts = tuple(int(part) for part in address.split("."))
            if len(parts) == 4 and all(0 <= part <= 255 for part in parts):
                return parts
        except (TypeError, ValueError):
            pass
        return (255, 255, 255, 255)

    def prefer_incoming_for_simultaneous_join(remote: TailscalePeerInfo) -> bool:
        local_ip = pairing_discovery.local_tailscale_ip
        # Lower Tailscale IPv4 keeps the incoming/host side (Player 1), higher
        # keeps its outgoing/join side (Player 2). Both therefore pick the same
        # physical TCP connection when they accidentally JOIN simultaneously.
        return bool(local_ip) and ip_key(local_ip) < ip_key(remote.address)

    def finish_connection(mode: str, peer: SecurePeer, player: int) -> tuple[str, SecurePeer, int]:
        pairing_discovery.close()
        if SOUND is not None:
            SOUND.play("connect")
        return mode, peer, player

    refresh()

    while True:
        clock.tick(FPS)

        incoming_peer = (
            host_job.result.peer
            if host_job.done.is_set() and host_job.result.peer is not None
            else None
        )
        outgoing_done = joining_job is not None and joining_job.done.is_set()
        outgoing_peer = (
            joining_job.result.peer
            if outgoing_done and joining_job is not None
            else None
        )

        # Normal case: the other player joined us while we were simply hosting.
        if incoming_peer is not None and joining_job is None:
            return finish_connection("host", incoming_peer, 1)

        # Simultaneous JOIN protection. We intentionally did NOT cancel our
        # listener when ENTER was pressed, so both possible TCP connections can
        # complete. The IP tie-break ensures each computer keeps opposite ends
        # of the same one.
        if incoming_peer is not None and joining_job is not None and joining_peer is not None:
            prefer_incoming = prefer_incoming_for_simultaneous_join(joining_peer)

            if prefer_incoming:
                joining_job.cancel.set()
                if outgoing_peer is not None and outgoing_peer is not incoming_peer:
                    outgoing_peer.close()
                return finish_connection("host", incoming_peer, 1)

            if outgoing_done:
                if outgoing_peer is not None:
                    incoming_peer.close()
                    actual_code = joining_job.result.fingerprint or code_value
                    save_trusted_peer(joining_peer, port, actual_code)
                    return finish_connection("join", outgoing_peer, 2)

                # Our preferred outgoing path failed, but an authenticated
                # incoming path is already alive. Use it rather than failing.
                return finish_connection("host", incoming_peer, 1)

        # Ordinary outgoing JOIN completed; no simultaneous incoming path won.
        if outgoing_done and joining_job is not None:
            if outgoing_peer is not None and joining_peer is not None:
                actual_code = joining_job.result.fingerprint or code_value
                save_trusted_peer(joining_peer, port, actual_code)
                return finish_connection("join", outgoing_peer, 2)

            status_message = "JOIN FAILED: " + (joining_job.result.error or "UNKNOWN ERROR")[:62]
            status_color = ERROR
            joining_job = None
            joining_peer = None

            # Usually the original host listener is still alive in v27. Only
            # recreate it if that listener itself has already terminated.
            if host_job.done.is_set() and host_job.result.peer is None:
                host_job = ConnectJob()
                host_job.start_host(port)
                pairing_discovery.close()
                pairing_discovery = PairingDiscovery(lambda: host_job.result.fingerprint)

        now = time.monotonic()
        if joining_job is None and now - last_refresh >= TAILSCALE_REFRESH_SECONDS:
            refresh()

        for event in game_events():
            if event.type == pygame.QUIT:
                host_job.cancel.set()
                if joining_job:
                    joining_job.cancel.set()
                pairing_discovery.close()
                return None

            if event.type != pygame.KEYDOWN:
                continue

            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                host_job.cancel.set()
                if joining_job:
                    joining_job.cancel.set()
                pairing_discovery.close()
                return None

            if handle_audio_hotkey(event):
                continue

            if joining_job is not None:
                continue

            if event.key == pygame.K_r:
                refresh()
                status_message = "PEER LIST REFRESHED"
                status_color = GREEN
                continue

            if event.key == pygame.K_c and host_job.result.fingerprint:
                copied, method = clipboard_set(host_job.result.fingerprint)
                status_message = (
                    f"PAIRING CODE COPIED USING {method}"
                    if copied else
                    "COULD NOT COPY — TYPE OR SEND THE CODE MANUALLY"
                )
                status_color = GREEN if copied else ERROR
                copy_status_until = time.monotonic() + 3.0
                continue

            # Number keys select a visible Tailscale computer.
            if pygame.K_1 <= event.key <= pygame.K_9:
                index = event.key - pygame.K_1
                if index < len(peers):
                    selected_index = index
                    selected = peers[index]
                    saved = trusted_code_for_peer(selected, port)
                    code_value = saved

                    if not selected.online:
                        status_message = f"{selected.name} APPEARS OFFLINE"
                        status_color = ERROR
                        continue

                    status_message = f"GETTING PAIRING CODE FROM {selected.name}..."
                    status_color = MUTED
                    present(screen)

                    fetched = pairing_discovery.request_code(selected.address)
                    if fetched:
                        code_value = fetched
                        save_trusted_peer(selected, port, fetched)
                        status_message = f"AUTO-PAIRED WITH {selected.name} — PRESS ENTER TO JOIN"
                        status_color = GREEN
                    elif saved:
                        status_message = f"{selected.name} IS TRUSTED — PRESS ENTER TO JOIN"
                        status_color = GREEN
                    else:
                        status_message = (
                            f"COULD NOT AUTO-PAIR WITH {selected.name} — "
                            "MAKE SURE v27+ IS OPEN ON BOTH COMPUTERS"
                        )
                        status_color = ERROR
                continue

            if selected_index is not None and selected_index < len(peers):
                selected = peers[selected_index]

                if event.key == pygame.K_RETURN:
                    if not selected.online:
                        status_message = f"{selected.name} APPEARS OFFLINE"
                        status_color = ERROR
                        continue

                    fingerprint = format_security_code(code_value)
                    if len(normalize_security_code(fingerprint)) < 16:
                        fetched = pairing_discovery.request_code(selected.address)
                        if fetched:
                            fingerprint = fetched
                            code_value = fetched
                            save_trusted_peer(selected, port, fetched)

                    if len(normalize_security_code(fingerprint)) < 16:
                        status_message = (
                            f"NO PAIRING CODE FROM {selected.name} — "
                            "OPEN v27+ ON BOTH COMPUTERS"
                        )
                        status_color = ERROR
                        continue

                    # v27 deliberately leaves host_job listening here. That is
                    # what removes the old "both pressed JOIN, both listeners
                    # disappeared" race.
                    joining_peer = selected
                    joining_job = ConnectJob()
                    joining_job.start_join(selected.address, port, fingerprint)
                    status_message = f"CONNECTING TO {selected.name}..."
                    status_color = GREEN
                    continue

        screen.fill(BG)
        draw_grid(screen)
        draw_text(screen, medium, "ONLINE LOBBY — TAILSCALE", (WIDTH // 2, 58), GREEN, center=True)

        local_label = self_name or "THIS COMPUTER"
        draw_text(screen, small, f"YOU: {local_label}   PORT {port}", (WIDTH // 2, 92), MUTED, center=True)
        draw_text(screen, small, tailscale_status, (WIDTH // 2, 116), GREEN if peers or self_name else ERROR, center=True)

        pygame.draw.rect(screen, DARK_PANEL, (60, 145, 880, 112), border_radius=10)
        draw_text(screen, small, "INVITE / HOST — AUTO-PAIR ENABLED", (80, 160), GREEN)
        if host_job.result.fingerprint:
            draw_text(screen, medium, host_job.result.fingerprint, (WIDTH // 2, 197), WHITE, center=True)
            draw_text(screen, small, "PAIRING IS AUTOMATIC WITH v27 PEERS    C = COPY FALLBACK", (WIDTH // 2, 231), MUTED, center=True)
        elif host_job.result.error:
            draw_text(screen, small, "HOST ERROR: " + host_job.result.error[:80], (WIDTH // 2, 202), ERROR, center=True)
        else:
            draw_text(screen, small, "CREATING SECURE INVITE...", (WIDTH // 2, 202), MUTED, center=True)

        pygame.draw.rect(screen, DARK_PANEL, (60, 274, 880, 238), border_radius=10)
        draw_text(screen, small, "JOIN — VISIBLE TAILSCALE COMPUTERS", (80, 289), GREEN)

        if not peers:
            draw_text(screen, small, "NO OTHER TAILSCALE COMPUTERS VISIBLE YET", (WIDTH // 2, 340), MUTED, center=True)
            draw_text(screen, small, "MAKE SURE BOTH COMPUTERS ARE ONLINE IN THE SAME TAILNET", (WIDTH // 2, 369), MUTED, center=True)
        else:
            y = 326
            for i, peer_info in enumerate(peers[:9]):
                selected = selected_index == i
                prefix = ">" if selected else " "
                state_word = "ONLINE" if peer_info.online else "OFFLINE"
                trusted = " • TRUSTED" if trusted_code_for_peer(peer_info, port) else ""
                color = WHITE if peer_info.online else MUTED
                if selected:
                    color = GREEN
                draw_text(
                    screen,
                    small,
                    f"{prefix} {i + 1}. {peer_info.name}   [{state_word}{trusted}]",
                    (95, y),
                    color,
                )
                y += 27

        if selected_index is not None and selected_index < len(peers):
            selected = peers[selected_index]
            saved = bool(trusted_code_for_peer(selected, port))
            code_display = code_value if code_value else ("SAVED" if saved else "_")
            draw_text(
                screen,
                small,
                f"AUTO PAIR FOR {selected.name}: {code_display}",
                (WIDTH // 2, 478),
                GREEN if saved else WHITE,
                center=True,
            )

        message = status_message
        if time.monotonic() > copy_status_until and status_message.startswith("PAIRING CODE COPIED"):
            message = "OPEN v27+ ONLINE LOBBY ON BOTH COMPUTERS"
        draw_text(screen, small, message, (WIDTH // 2, 535), status_color, center=True)
        draw_text(
            screen,
            small,
            "1-9 SELECT PEER + AUTO-PAIR   ENTER JOIN   M MUSIC   N SFX   ESC BACK",
            (WIDTH // 2, 574),
            MUTED,
            center=True,
        )
        present(screen)



def run_match(screen, fonts, mode: str, peer: Optional[SecurePeer], local_player: int) -> None:
    clock = pygame.time.Clock()
    accumulator = 0.0
    running = True

    if mode in ("local", "easy", "medium", "hard"):
        state = initial_world()
        session = RollbackSession(1, None, is_host=True)
        render_state = RenderState.from_world(state)
        cpu = CpuController(mode) if mode in ("easy", "medium", "hard") else None
        label = {
            "local": "LOCAL TWO PLAYER",
            "easy": "COMPUTER — EASY",
            "medium": "COMPUTER — MEDIUM",
            "hard": "COMPUTER — HARD",
        }[mode]
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            for event in game_events():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        running = False
                    elif handle_audio_hotkey(event):
                        pass
                    elif event.key == pygame.K_r and state.winner:
                        state = initial_world()
                        render_state = RenderState.from_world(state)
                        if cpu:
                            cpu = CpuController(mode)

            accumulator += dt
            while accumulator >= FIXED_DT:
                p1 = keyboard_input_for(1)
                p2 = keyboard_input_for(2) if mode == "local" else cpu.update(state)
                before = state.clone()
                step_world(state, p1, p2)
                if SOUND is not None:
                    SOUND.observe(before, state)
                render_state.update(state, None)
                accumulator -= FIXED_DT

            session.state = state
            draw_game(screen, session, fonts, label, render_state)
            present(screen)
        return

    session = RollbackSession(local_player, peer, is_host=(mode == "host"))
    mode_label = "SECURE HOST — PLAYER 1" if local_player == 1 else "SECURE GUEST — PLAYER 2"
    render_state = RenderState.from_world(session.state)

    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in game_events():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    running = False
                elif handle_audio_hotkey(event):
                    pass
                elif event.key == pygame.K_r and session.state.winner:
                    session.request_restart()
                    render_state = RenderState.from_world(session.state)

        accumulator += dt
        while accumulator >= FIXED_DT:
            before = session.state.clone()
            session.advance(keyboard_input_for(local_player))
            if SOUND is not None:
                SOUND.observe(before, session.state)
            render_state.update(session.state, local_player)
            accumulator -= FIXED_DT

        draw_game(screen, session, fonts, mode_label, render_state)
        present(screen)

    session.close()
    if peer:
        peer.close()

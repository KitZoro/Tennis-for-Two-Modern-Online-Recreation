from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import pygame

import ui
from config import *
from cpu import CpuController
from game import RenderState, initial_world, step_world
from rollback import RollbackSession

STORY_SAVE = CONFIG_DIR / "story_progress.json"


@dataclass(frozen=True)
class Chapter:
    title: str
    subtitle: str
    cpu_level: str
    intro: tuple[tuple[str, str], ...]
    victory: tuple[tuple[str, str], ...]
    defeat: tuple[tuple[str, str], ...]


CHAPTERS: tuple[Chapter, ...] = (
    Chapter(
        "1 — THE OLD SCREEN",
        "Edwin finds a game that history almost left behind.",
        "easy",
        (
            ("EDWIN", "So this is Tennis for Two. 1958. One glowing screen, one net, one ball."),
            ("EDWIN", "No loot boxes. No season pass. Apparently civilization survived."),
            ("EDWIN", "Let's see if the old thing still knows how to play."),
            ("SYSTEM", "A/D move. W/S change angle. Q/E change power. SPACE hits."),
            ("EDWIN", "First lesson: timing beats panic. Probably."),
        ),
        (
            ("EDWIN", "It still works."),
            ("EDWIN", "That's the dangerous part. Now I'm wondering what else it can do."),
        ),
        (
            ("EDWIN", "Apparently the museum exhibit has hands."),
            ("EDWIN", "Again. I refuse to be defeated by a line and a circle."),
        ),
    ),
    Chapter(
        "2 — IT IS NOT PONG",
        "A familiar accusation appears.",
        "medium",
        (
            ("VOICE", "Cute Pong remake."),
            ("EDWIN", "Pong?"),
            ("VOICE", "You know. Two paddles. Ball. Beep."),
            ("EDWIN", "This game is from 1958."),
            ("VOICE", "Still looks like Pong."),
            ("EDWIN", "Fine. History lesson by tennis ball."),
        ),
        (
            ("EDWIN", "For the record: Tennis for Two, 1958."),
            ("VOICE", "...fine. Not Pong."),
            ("EDWIN", "I will treasure this victory forever."),
        ),
        (
            ("VOICE", "Pong wins."),
            ("EDWIN", "You have made this personal."),
        ),
    ),
    Chapter(
        "3 — THE INTERNET HAS OPINIONS",
        "The tennis is easy. The network is not.",
        "medium",
        (
            ("EDWIN", "The original machine had one enormous technological advantage."),
            ("EDWIN", "It did not have to deal with the internet."),
            ("SYSTEM", "SIMULATED REMOTE OPPONENT CONNECTED."),
            ("EDWIN", "If the ball teleports, I'm blaming the packets."),
            ("EDWIN", "If I miss normally, I'm also blaming the packets."),
        ),
        (
            ("SYSTEM", "MATCH COMPLETE."),
            ("EDWIN", "See? Long-distance tennis."),
            ("EDWIN", "Now all we need is for reality to behave exactly like this test."),
        ),
        (
            ("EDWIN", "The internet has won this round."),
            ("EDWIN", "Unfortunately for it, we have logs."),
        ),
    ),
    Chapter(
        "4 — RETURN OF THE TENNIS",
        "One last match to prove the old game can live again.",
        "hard",
        (
            ("EDWIN", "People rebuilt Tennis for Two as history."),
            ("EDWIN", "I want it to be something people actually play."),
            ("EDWIN", "Local. Online. CPU. Story mode. Still simple where it matters."),
            ("EDWIN", "So here's the question."),
            ("EDWIN", "Can a game from 1958 come back as a modern game?"),
            ("SYSTEM", "FINAL OPPONENT: HARD CPU"),
        ),
        (
            ("EDWIN", "Yes."),
            ("EDWIN", "Apparently it can."),
            ("SYSTEM", "STORY PREVIEW COMPLETE"),
            ("EDWIN", "The tennis is back. Now we keep building."),
        ),
        (
            ("EDWIN", "Okay. The future of Tennis for Two can wait five minutes."),
            ("EDWIN", "Rematch."),
        ),
    ),
)


def _load_progress() -> dict:
    default = {"unlocked": 1, "completed": []}
    try:
        data = json.loads(STORY_SAVE.read_text(encoding="utf-8"))
        completed = [
            int(x) for x in data.get("completed", [])
            if isinstance(x, int) or str(x).isdigit()
        ]
        unlocked = max(1, min(len(CHAPTERS), int(data.get("unlocked", 1))))
        return {"unlocked": unlocked, "completed": completed}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return default


def _save_progress(progress: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        STORY_SAVE.write_text(json.dumps(progress, indent=2), encoding="utf-8")
    except OSError:
        pass


def _wrap(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = current + " " + word
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines




def _draw_edwin_bunny(screen: pygame.Surface, x: int, y: int, scale: float = 1.0, expression: str = "neutral") -> None:
    """Draw Edwin Skycross as a stylized Pygame bunny portrait.

    Pure vector art: no external texture/model dependencies.
    """
    def P(dx: float, dy: float) -> tuple[int, int]:
        return (int(x + dx * scale), int(y + dy * scale))

    fur = (150, 154, 164)
    fur_dark = (99, 105, 116)
    white = (235, 236, 240)
    tip = (30, 33, 39)
    purple = (157, 103, 255)
    jacket = (38, 54, 67)
    jacket_hi = (61, 86, 103)
    outline = (19, 27, 32)

    # Shoulders/jacket
    pygame.draw.ellipse(screen, outline, (*P(-66, 48), int(132*scale), int(80*scale)))
    pygame.draw.ellipse(screen, jacket, (*P(-61, 51), int(122*scale), int(72*scale)))
    pygame.draw.polygon(screen, jacket_hi, [P(-18, 53), P(0, 77), P(18, 53), P(10, 112), P(-10, 112)])

    # Tall rabbit ears, black tipped.
    left_ear = [P(-43, -89), P(-22, -105), P(-12, -35), P(-35, -25)]
    right_ear = [P(43, -89), P(22, -105), P(12, -35), P(35, -25)]
    pygame.draw.polygon(screen, outline, left_ear)
    pygame.draw.polygon(screen, outline, right_ear)
    pygame.draw.polygon(screen, fur, [P(-39, -84), P(-25, -98), P(-16, -37), P(-32, -30)])
    pygame.draw.polygon(screen, fur, [P(39, -84), P(25, -98), P(16, -37), P(32, -30)])
    pygame.draw.polygon(screen, tip, [P(-39, -84), P(-25, -98), P(-21, -73), P(-35, -68)])
    pygame.draw.polygon(screen, tip, [P(39, -84), P(25, -98), P(21, -73), P(35, -68)])

    # Head and cheek fluff.
    pygame.draw.ellipse(screen, outline, (*P(-54, -42), int(108*scale), int(113*scale)))
    pygame.draw.ellipse(screen, fur, (*P(-50, -38), int(100*scale), int(105*scale)))
    pygame.draw.polygon(screen, fur, [P(-45, 11), P(-62, 25), P(-42, 31)])
    pygame.draw.polygon(screen, fur, [P(45, 11), P(62, 25), P(42, 31)])

    # White muzzle.
    pygame.draw.ellipse(screen, white, (*P(-34, 10), int(68*scale), int(46*scale)))
    pygame.draw.ellipse(screen, white, (*P(-25, 28), int(50*scale), int(31*scale)))

    # Eyes.
    eye_y = -4
    for ex in (-23, 23):
        pygame.draw.ellipse(screen, outline, (*P(ex-10, eye_y-12), int(20*scale), int(26*scale)))
        pygame.draw.ellipse(screen, purple, (*P(ex-7, eye_y-9), int(14*scale), int(20*scale)))
        pygame.draw.circle(screen, (245,245,255), P(ex-2, eye_y-5), max(1, int(3*scale)))

    # Nose and mouth expression.
    pygame.draw.polygon(screen, tip, [P(-5, 20), P(5, 20), P(0, 27)])
    if expression == "smile":
        pygame.draw.arc(screen, outline, (*P(-18, 19), int(18*scale), int(24*scale)), 5.0, 6.25, max(1, int(2*scale)))
        pygame.draw.arc(screen, outline, (*P(0, 19), int(18*scale), int(24*scale)), 3.18, 4.45, max(1, int(2*scale)))
    elif expression == "annoyed":
        pygame.draw.line(screen, outline, P(-28, -16), P(-14, -20), max(1, int(3*scale)))
        pygame.draw.line(screen, outline, P(28, -16), P(14, -20), max(1, int(3*scale)))
        pygame.draw.line(screen, outline, P(-10, 40), P(10, 40), max(1, int(2*scale)))
    else:
        pygame.draw.arc(screen, outline, (*P(-15, 27), int(30*scale), int(19*scale)), 0.2, 2.95, max(1, int(2*scale)))

    # A small green accent pin that ties the portrait into the game UI.
    pygame.draw.circle(screen, GREEN, P(0, 85), max(2, int(4*scale)))


def _draw_voice_icon(screen: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.circle(screen, MUTED, (x, y), 54, 3)
    for i, h in enumerate((16, 32, 48, 28, 40, 20)):
        bx = x - 35 + i * 14
        pygame.draw.line(screen, WHITE, (bx, y-h//2), (bx, y+h//2), 3)


def _draw_system_icon(screen: pygame.Surface, x: int, y: int) -> None:
    rect = pygame.Rect(x-55, y-43, 110, 86)
    pygame.draw.rect(screen, (16, 25, 31), rect, border_radius=10)
    pygame.draw.rect(screen, GREEN, rect, 3, border_radius=10)
    pygame.draw.line(screen, GREEN, (x-31, y-8), (x-12, y+4), 3)
    pygame.draw.line(screen, GREEN, (x-12, y+4), (x-31, y+16), 3)
    pygame.draw.line(screen, GREEN, (x-3, y+17), (x+30, y+17), 3)


def _dialogue(screen, fonts, lines: tuple[tuple[str, str], ...]) -> bool:
    _, medium, small = fonts
    clock = pygame.time.Clock()
    index = 0

    while index < len(lines):
        clock.tick(FPS)
        for event in ui.game_events():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    return False
                if ui.handle_audio_hotkey(event):
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    index += 1
                    if index >= len(lines):
                        return True

        speaker, text = lines[index]
        screen.fill(BG)
        ui.draw_grid(screen)
        pygame.draw.rect(screen, (31, 43, 50), (45, 48, WIDTH - 90, HEIGHT - 96), 3, border_radius=24)

        # Story portraits are drawn directly in Pygame, so Story Mode has no
        # external art/model dependency.
        if speaker == "EDWIN":
            mood = "smile" if any(word in text.lower() for word in ("works", "yes", "victory", "treasure")) else ("annoyed" if any(word in text.lower() for word in ("pong", "personal", "defeated")) else "neutral")
            _draw_edwin_bunny(screen, 145, 195, 0.78, mood)
            ui.draw_text(screen, small, "EDWIN SKYCROSS", (145, 305), GREEN, center=True)
        elif speaker == "SYSTEM":
            _draw_system_icon(screen, 145, 195)
            ui.draw_text(screen, small, "SYSTEM", (145, 275), GREEN, center=True)
        else:
            _draw_voice_icon(screen, 145, 195)
            ui.draw_text(screen, small, speaker, (145, 275), WHITE, center=True)

        pygame.draw.rect(screen, DARK_PANEL, (245, 115, 675, 330), border_radius=16)
        ui.draw_text(screen, medium, speaker, (280, 145), GREEN if speaker == "EDWIN" else WHITE)
        y = 205
        for wrapped in _wrap(medium, text, 590):
            ui.draw_text(screen, medium, wrapped, (280, y), WHITE)
            y += 38

        ui.draw_text(screen, small, f"{index + 1}/{len(lines)}", (885, 415), MUTED, center=True)
        ui.draw_text(screen, small, "ENTER / SPACE CONTINUE    ESC BACK", (WIDTH // 2, 520), MUTED, center=True)
        ui.present(screen)

    return True


def _result_screen(screen, fonts, title: str, body: str, allow_retry: bool) -> str:
    _, medium, small = fonts
    clock = pygame.time.Clock()
    while True:
        clock.tick(FPS)
        for event in ui.game_events():
            if event.type == pygame.QUIT:
                return "exit"
            if event.type == pygame.KEYDOWN:
                if ui.handle_audio_hotkey(event):
                    continue
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    return "exit"
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return "retry" if allow_retry else "continue"

        screen.fill(BG)
        ui.draw_grid(screen)
        ui.draw_text(screen, medium, title, (WIDTH // 2, 235), GREEN, center=True)
        ui.draw_text(screen, small, body, (WIDTH // 2, 290), WHITE, center=True)
        prompt = "ENTER RETRY    ESC STORY MENU" if allow_retry else "ENTER CONTINUE"
        ui.draw_text(screen, small, prompt, (WIDTH // 2, 355), MUTED, center=True)
        ui.present(screen)


def _play_challenge(screen, fonts, chapter: Chapter) -> Optional[bool]:
    """Return True on win, False on loss, None if player exits."""
    clock = pygame.time.Clock()
    accumulator = 0.0
    state = initial_world()
    session = RollbackSession(1, None, is_host=True)
    render_state = RenderState.from_world(state)
    cpu = CpuController(chapter.cpu_level)

    try:
        while True:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)
            for event in ui.game_events():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        return None
                    if ui.handle_audio_hotkey(event):
                        continue

            accumulator += dt
            while accumulator >= FIXED_DT and not state.winner:
                p1 = ui.keyboard_input_for(1)
                p2 = cpu.update(state)
                before = state.clone()
                step_world(state, p1, p2)
                if ui.SOUND is not None:
                    ui.SOUND.observe(before, state)
                render_state.update(state, None)
                accumulator -= FIXED_DT

            session.state = state
            ui.draw_game(screen, session, fonts, f"STORY — {chapter.title}", render_state)
            _, _, small = fonts
            ui.draw_text(screen, small, "EDWIN = PLAYER 1", (WIDTH // 2, 122), GREEN, center=True)
            ui.present(screen)

            if state.winner:
                return state.winner == 1
    finally:
        session.close()


def _run_chapter(screen, fonts, chapter_index: int, progress: dict) -> None:
    chapter = CHAPTERS[chapter_index]
    if not _dialogue(screen, fonts, chapter.intro):
        return

    while True:
        won = _play_challenge(screen, fonts, chapter)
        if won is None:
            return

        if won:
            if not _dialogue(screen, fonts, chapter.victory):
                return
            if chapter_index not in progress["completed"]:
                progress["completed"].append(chapter_index)
            progress["unlocked"] = min(
                len(CHAPTERS), max(progress["unlocked"], chapter_index + 2)
            )
            _save_progress(progress)
            _result_screen(screen, fonts, "CHAPTER COMPLETE", "Progress saved automatically.", False)
            return

        if not _dialogue(screen, fonts, chapter.defeat):
            return
        choice = _result_screen(screen, fonts, "MATCH LOST", "Edwin would like another attempt.", True)
        if choice != "retry":
            return


def story_menu(screen, fonts) -> None:
    _, medium, small = fonts
    progress = _load_progress()
    clock = pygame.time.Clock()

    while True:
        clock.tick(FPS)
        for event in ui.game_events():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    return
                if ui.handle_audio_hotkey(event):
                    continue
                if event.key == pygame.K_r:
                    progress = {"unlocked": 1, "completed": []}
                    _save_progress(progress)
                    continue
                if pygame.K_1 <= event.key <= pygame.K_9:
                    idx = event.key - pygame.K_1
                    if idx < len(CHAPTERS) and idx < progress["unlocked"]:
                        _run_chapter(screen, fonts, idx, progress)

        screen.fill(BG)
        ui.draw_grid(screen)
        ui.draw_text(screen, medium, "STORY MODE — EDWIN SKYCROSS", (WIDTH // 2, 55), GREEN, center=True)
        ui.draw_text(screen, small, "Playable 2D story — no external art or 3D dependencies", (WIDTH // 2, 88), MUTED, center=True)

        y = 145
        for i, chapter in enumerate(CHAPTERS):
            unlocked = i < progress["unlocked"]
            completed = i in progress["completed"]
            pygame.draw.rect(screen, DARK_PANEL, (110, y - 22, 780, 76), border_radius=10)
            if unlocked:
                marker = "✓" if completed else str(i + 1)
                color = GREEN if completed else WHITE
                ui.draw_text(screen, medium, f"{marker}  {chapter.title}", (145, y), color)
                ui.draw_text(screen, small, chapter.subtitle, (145, y + 31), MUTED)
            else:
                ui.draw_text(screen, medium, f"LOCKED — CHAPTER {i + 1}", (145, y), MUTED)
                ui.draw_text(screen, small, "Complete the previous chapter to unlock.", (145, y + 31), MUTED)
            y += 92

        ui.draw_text(screen, small, "1-4 PLAY CHAPTER    R RESET STORY SAVE    ESC BACK", (WIDTH // 2, 548), MUTED, center=True)
        ui.present(screen)


def main_menu(screen, fonts) -> Optional[str]:
    """Main menu with Story Mode added without changing the online code."""
    large, medium, small = fonts
    options = [
        ("1", "STORY MODE — EDWIN SKYCROSS", "story"),
        ("2", "LOCAL TWO PLAYER", "local"),
        ("3", "COMPUTER — EASY", "easy"),
        ("4", "COMPUTER — MEDIUM", "medium"),
        ("5", "COMPUTER — HARD", "hard"),
        ("6", "ONLINE LOBBY — TAILSCALE", "online"),
        ("7", "NETWORK TEST — ONE PC", "nettest"),
        ("8", "AUDIO SETTINGS", "audio"),
    ]
    clock = pygame.time.Clock()

    while True:
        clock.tick(FPS)
        for event in ui.game_events():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if ui.handle_audio_hotkey(event):
                    continue
                for key, _, mode in options:
                    if event.unicode == key:
                        if mode == "audio": # added
                            audio_menu(screen, fonts) # added
                        else: # added
                            return mode

        screen.fill(BG)
        ui.draw_grid(screen)
        ui.draw_text(screen, large, "TENNIS FOR TWO", (WIDTH // 2, 58), GREEN, center=True)
        ui.draw_text(screen, small, "1958 GAMEPLAY — MODERN FEATURES — EDWIN SKYCROSS STORY", (WIDTH // 2, 94), MUTED, center=True)

        y = 132
        for key, label, _ in options:
            pygame.draw.rect(screen, DARK_PANEL, (210, y - 19, 580, 38), border_radius=9)
            ui.draw_text(screen, medium, f"{key}  {label}", (WIDTH // 2, y), WHITE, center=True)
            y += 46

        if ui.SOUND is not None:
            music_state = "OFF" if ui.SOUND.music_muted else "ON"
            sfx_state = "OFF" if ui.SOUND.sfx_muted else "ON"
            ui.draw_text(screen, small, f"MUSIC {music_state}: {ui.SOUND.music_name}    SFX {sfx_state}", (WIDTH // 2, 482), MUTED, center=True)

        ui.draw_text(screen, small, "F11 FULLSCREEN   M MUSIC   N SFX   F5 RELOAD MUSIC   ESC QUITS", (WIDTH // 2, 530), MUTED, center=True)
        ui.present(screen)

# added
def audio_menu(screen, fonts) -> None:
    large, medium, small = fonts
    clock = pygame.time.Clock()

    selected = 0
    options = ["SFX", "MUSIC"]

    while True:
        clock.tick(FPS)

        for event in ui.game_events():
            if event.type == pygame.QUIT:
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return

                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)

                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)

                elif event.key == pygame.K_LEFT:
                    if ui.SOUND is not None:
                        if selected == 0:
                            ui.SOUND.set_sfx_volume(ui.SOUND.sfx_volume - 0.05)
                        else:
                            ui.SOUND.set_music_volume(ui.SOUND.music_volume - 0.05)

                elif event.key == pygame.K_RIGHT:
                    if ui.SOUND is not None:
                        if selected == 0:
                            ui.SOUND.set_sfx_volume(ui.SOUND.sfx_volume + 0.05)
                        else:
                            ui.SOUND.set_music_volume(ui.SOUND.music_volume + 0.05)

        screen.fill(BG)
        ui.draw_grid(screen)

        ui.draw_text(
            screen,
            large,
            "AUDIO SETTINGS",
            (WIDTH // 2, 100),
            GREEN,
            center=True,
        )

        if ui.SOUND is not None:
            values = [
                ui.SOUND.sfx_volume,
                ui.SOUND.music_volume,
            ]

            y = 220

            for i, label in enumerate(options):
                value = values[i]
                percent = round(value * 100)

                color = GREEN if i == selected else WHITE

                ui.draw_text(
                    screen,
                    medium,
                    f"{label}: {percent}%",
                    (WIDTH // 2, y),
                    color,
                    center=True,
                )

                bar_x = WIDTH // 2 - 200
                bar_y = y + 35
                bar_width = 400
                bar_height = 18

                pygame.draw.rect(
                    screen,
                    DARK_PANEL,
                    (bar_x, bar_y, bar_width, bar_height),
                    border_radius=8,
                )

                pygame.draw.rect(
                    screen,
                    GREEN,
                    (
                        bar_x,
                        bar_y,
                        int(bar_width * value),
                        bar_height,
                    ),
                    border_radius=8,
                )

                y += 120

        ui.draw_text(
            screen,
            small,
            "UP/DOWN SELECT   LEFT/RIGHT CHANGE   ESC BACK",
            (WIDTH // 2, 520),
            MUTED,
            center=True,
        )

        ui.present(screen)
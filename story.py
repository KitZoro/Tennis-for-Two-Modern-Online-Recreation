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

        # Placeholder oscilloscope portrait until final Edwin art is added.
        pygame.draw.circle(screen, GREEN, (145, 190), 62, 3)
        pygame.draw.circle(screen, WHITE, (125, 178), 5)
        pygame.draw.circle(screen, WHITE, (165, 178), 5)
        pygame.draw.arc(screen, GREEN, (112, 180, 66, 50), 3.35, 6.05, 3)
        ui.draw_text(screen, small, "EDWIN", (145, 275), GREEN, center=True)

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
        ui.draw_text(screen, small, "A playable story preview built around the original tennis rules", (WIDTH // 2, 88), MUTED, center=True)

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

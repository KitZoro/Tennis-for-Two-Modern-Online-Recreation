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
    Chapter(
        "5 — BROTHERHOOD",
        "A tribute to Sonic and Tails Brotherhood — especially Chapter 9.",
        "hard",
        (
            ("SYSTEM", "TRIBUTE CHAPTER — Inspired by the fan project Sonic and Tails Brotherhood."),
            ("GUARD", "Jim and Mick are in the city."),
            ("KIT", "How dare they?"),
            ("EDWIN", "I don't understand."),
            ("GUARD", "Kit banished them."),
            ("EDWIN", "For what?"),
            ("KIT", "Bullying."),
            ("GUARD", "What do you want done?"),
            ("KIT", "I want Edwin to beat them."),
            ("EDWIN", "Of course you do."),
            ("SYSTEM", "JIM AND MICK CHALLENGE — Win the match as Edwin."),
        ),
        (
            ("GUARD", "Well done, sir."),
            ("KIT", "Now they know to never mistreat orphans ever again."),
            ("EDWIN", "That explanation would have been useful before the match."),
            ("KIT", "Jim. Mick. What are your thoughts on Tails?"),
            ("JIM", "He is a mistake."),
            ("MICK", "Yeah."),
            ("KIT", "Then I sentence you to prison like Edwin wanted."),
            ("EDWIN", "Wait. I wanted what?"),
            ("EDWIN", "Hold on. Are you copying something?"),
            ("KIT", "Yes. Jim and Mick are bullies in Sonic and Tails Brotherhood. I'm punishing them for Tails."),
            ("EDWIN", "Chapter 9. Eggman sent robots after them. Sonic and Tails saved them, and they still resented Tails for saving them."),
            ("KIT", "Exactly."),
            ("EDWIN", "That is spectacularly ungrateful."),
            ("KIT", "Thank you. Now you understand the assignment."),
            ("EDWIN", "I understand the grudge. Those are not the same thing."),
            ("SYSTEM", "TRIBUTE COMPLETE — Sonic and Tails Brotherhood / Chapter 9."),
        ),
        (
            ("KIT", "You lost to Jim and Mick?"),
            ("EDWIN", "I was distracted by the fact that I still don't know why they're here."),
            ("KIT", "Rematch. This is for Tails."),
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



def _draw_kit_fox(screen: pygame.Surface, x: int, y: int, scale: float = 1.0, expression: str = "smirk") -> None:
    """Draw Kit's platinum fox fursona with glowing blue eyes."""
    def P(dx: float, dy: float) -> tuple[int, int]:
        return (int(x + dx * scale), int(y + dy * scale))

    platinum = (220, 225, 232)
    platinum_shadow = (165, 174, 185)
    white = (247, 249, 252)
    outline = (22, 28, 35)
    blue = (55, 185, 255)
    blue_glow = (125, 220, 255)
    shirt = (42, 48, 63)

    # Shoulders.
    pygame.draw.ellipse(screen, outline, (*P(-68, 47), int(136*scale), int(82*scale)))
    pygame.draw.ellipse(screen, shirt, (*P(-63, 51), int(126*scale), int(74*scale)))

    # Fox ears.
    pygame.draw.polygon(screen, outline, [P(-48,-34), P(-42,-96), P(-8,-50)])
    pygame.draw.polygon(screen, outline, [P(48,-34), P(42,-96), P(8,-50)])
    pygame.draw.polygon(screen, platinum, [P(-43,-39), P(-39,-87), P(-13,-49)])
    pygame.draw.polygon(screen, platinum, [P(43,-39), P(39,-87), P(13,-49)])
    pygame.draw.polygon(screen, platinum_shadow, [P(-37,-47), P(-36,-75), P(-21,-51)])
    pygame.draw.polygon(screen, platinum_shadow, [P(37,-47), P(36,-75), P(21,-51)])

    # Head and cheek tufts.
    pygame.draw.ellipse(screen, outline, (*P(-54,-48), int(108*scale), int(116*scale)))
    pygame.draw.ellipse(screen, platinum, (*P(-50,-44), int(100*scale), int(108*scale)))
    pygame.draw.polygon(screen, platinum, [P(-44,8),P(-63,24),P(-40,31)])
    pygame.draw.polygon(screen, platinum, [P(44,8),P(63,24),P(40,31)])

    # Muzzle.
    pygame.draw.ellipse(screen, white, (*P(-31,12), int(62*scale), int(43*scale)))
    pygame.draw.polygon(screen, outline, [P(-5,18),P(5,18),P(0,25)])

    # Glowing blue eyes: halo + core.
    for ex in (-22,22):
        pygame.draw.circle(screen, blue_glow, P(ex,-6), max(3,int(13*scale)))
        pygame.draw.ellipse(screen, outline, (*P(ex-10,-18),int(20*scale),int(27*scale)))
        pygame.draw.ellipse(screen, blue, (*P(ex-7,-15),int(14*scale),int(21*scale)))
        pygame.draw.circle(screen, white, P(ex-2,-10), max(1,int(3*scale)))

    # Expression.
    if expression == "annoyed":
        pygame.draw.line(screen, outline, P(-29,-19), P(-14,-23), max(1,int(3*scale)))
        pygame.draw.line(screen, outline, P(29,-19), P(14,-23), max(1,int(3*scale)))
        pygame.draw.line(screen, outline, P(-11,39), P(11,39), max(1,int(2*scale)))
    else:
        pygame.draw.arc(screen, outline, (*P(-15,27),int(30*scale),int(17*scale)), 3.35, 5.95, max(1,int(2*scale)))


def _draw_simple_character(screen: pygame.Surface, x: int, y: int, label: str) -> None:
    """Simple neutral portrait for tribute NPCs without pretending they have a canonical design."""
    pygame.draw.circle(screen, (38, 47, 56), (x, y), 56)
    pygame.draw.circle(screen, (190, 198, 207), (x, y-7), 36)
    pygame.draw.circle(screen, (35, 40, 47), (x-13, y-12), 4)
    pygame.draw.circle(screen, (35, 40, 47), (x+13, y-12), 4)
    pygame.draw.line(screen, (35, 40, 47), (x-12, y+11), (x+12, y+11), 3)

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
            mood = "smile" if any(word in text.lower() for word in ("works", "yes", "victory", "treasure")) else ("annoyed" if any(word in text.lower() for word in ("pong", "personal", "defeated", "grudge")) else "neutral")
            _draw_edwin_bunny(screen, 145, 195, 0.78, mood)
            ui.draw_text(screen, small, "EDWIN SKYCROSS", (145, 305), GREEN, center=True)
        elif speaker == "KIT":
            mood = "annoyed" if any(word in text.lower() for word in ("how dare", "prison", "bullying")) else "smirk"
            _draw_kit_fox(screen, 145, 195, 0.78, mood)
            ui.draw_text(screen, small, "KIT ZORO", (145, 305), (90, 200, 255), center=True)
        elif speaker in ("JIM", "MICK", "GUARD"):
            _draw_simple_character(screen, 145, 195, speaker)
            ui.draw_text(screen, small, speaker, (145, 275), WHITE, center=True)
        elif speaker == "SYSTEM":
            _draw_system_icon(screen, 145, 195)
            ui.draw_text(screen, small, "SYSTEM", (145, 275), GREEN, center=True)
        else:
            _draw_voice_icon(screen, 145, 195)
            ui.draw_text(screen, small, speaker, (145, 275), WHITE, center=True)

        pygame.draw.rect(screen, DARK_PANEL, (245, 115, 675, 330), border_radius=16)
        speaker_color = GREEN if speaker == "EDWIN" else ((90, 200, 255) if speaker == "KIT" else WHITE)
        ui.draw_text(screen, medium, speaker, (280, 145), speaker_color)
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
    selected = max(0, min(progress["unlocked"] - 1, len(CHAPTERS) - 1))
    view_start = 0
    visible_rows = 5

    def clamp_view() -> None:
        nonlocal view_start, selected
        selected = max(0, min(selected, len(CHAPTERS) - 1))
        if selected < view_start:
            view_start = selected
        elif selected >= view_start + visible_rows:
            view_start = selected - visible_rows + 1
        max_start = max(0, len(CHAPTERS) - visible_rows)
        view_start = max(0, min(view_start, max_start))

    def try_play(index: int) -> None:
        nonlocal progress
        if 0 <= index < len(CHAPTERS) and index < progress["unlocked"]:
            _run_chapter(screen, fonts, index, progress)
            progress = _load_progress()

    clamp_view()

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
                    selected = 0
                    view_start = 0
                    continue
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected -= 1
                    clamp_view()
                    continue
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected += 1
                    clamp_view()
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    try_play(selected)
                    clamp_view()
                    continue
                if pygame.K_1 <= event.key <= pygame.K_9:
                    idx = event.key - pygame.K_1
                    if idx < len(CHAPTERS):
                        selected = idx
                        clamp_view()
                        try_play(idx)
                        clamp_view()

        screen.fill(BG)
        ui.draw_grid(screen)
        ui.draw_text(screen, medium, "STORY MODE — EDWIN SKYCROSS", (WIDTH // 2, 50), GREEN, center=True)
        ui.draw_text(screen, small, "Playable 2D story — Chapter 5: Sonic and Tails Brotherhood tribute", (WIDTH // 2, 82), MUTED, center=True)

        list_y = 128
        row_step = 78
        panel_x = 110
        panel_w = 780
        panel_h = 66

        end = min(len(CHAPTERS), view_start + visible_rows)
        for row, i in enumerate(range(view_start, end)):
            chapter = CHAPTERS[i]
            unlocked = i < progress["unlocked"]
            completed = i in progress["completed"]
            y = list_y + row * row_step
            rect = pygame.Rect(panel_x, y, panel_w, panel_h)
            is_selected = i == selected
            fill = (24, 46, 54) if is_selected else DARK_PANEL
            border = GREEN if is_selected else GRID
            pygame.draw.rect(screen, fill, rect, border_radius=10)
            pygame.draw.rect(screen, border, rect, width=2 if is_selected else 1, border_radius=10)

            if unlocked:
                marker = "✓" if completed else str(i + 1)
                color = GREEN if completed else WHITE
                ui.draw_text(screen, medium, f"{marker}  {chapter.title}", (145, y + 10), color)
                ui.draw_text(screen, small, chapter.subtitle, (145, y + 37), MUTED)
            else:
                ui.draw_text(screen, medium, f"LOCKED — CHAPTER {i + 1}", (145, y + 10), MUTED)
                ui.draw_text(screen, small, "Complete the previous chapter to unlock.", (145, y + 37), MUTED)

        if len(CHAPTERS) > visible_rows:
            track = pygame.Rect(906, list_y, 8, row_step * visible_rows - 12)
            pygame.draw.rect(screen, DARK_PANEL, track, border_radius=4)
            handle_h = max(18, int(track.h * (visible_rows / len(CHAPTERS))))
            max_offset = max(1, len(CHAPTERS) - visible_rows)
            handle_y = track.y if max_offset == 0 else track.y + int((track.h - handle_h) * (view_start / max_offset))
            pygame.draw.rect(screen, GREEN, (track.x, handle_y, track.w, handle_h), border_radius=4)

        selected_chapter = CHAPTERS[selected]
        status = "READY" if selected < progress["unlocked"] else "LOCKED"
        footer_rect = pygame.Rect(110, 530, 780, 40)
        pygame.draw.rect(screen, DARK_PANEL, footer_rect, border_radius=10)
        pygame.draw.rect(screen, GRID, footer_rect, width=1, border_radius=10)
        ui.draw_text(screen, small, f"SELECTED: {selected_chapter.title}    STATUS: {status}", (128, 543), WHITE)
        ui.draw_text(screen, small, "↑/↓ MOVE    ENTER PLAY    1-5 JUMP    R RESET SAVE    ESC BACK", (WIDTH // 2, 585), MUTED, center=True)
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
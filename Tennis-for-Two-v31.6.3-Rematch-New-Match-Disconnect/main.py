from __future__ import annotations

import pygame

import story
import ui
from audio import SoundManager
from config import AUDIO_SAMPLE_RATE, WIDTH, HEIGHT

def main() -> None:
    print("Starting Tennis for Two v30 FULL + Story Pack")
    pygame.mixer.pre_init(AUDIO_SAMPLE_RATE, -16, 1, 512)
    pygame.init()
    ui.SOUND = SoundManager()

    try:
        pygame.scrap.init()
    except pygame.error:
        pass

    pygame.display.set_caption("Tennis for Two — v30 FULL + Story Pack")
    ui._open_display(False)

    screen = pygame.Surface((WIDTH, HEIGHT)).convert()
    fonts = (
        pygame.font.SysFont("consolas", 42),
        pygame.font.SysFont("consolas", 27),
        pygame.font.SysFont("consolas", 17),
    )

    while True:
        mode = story.main_menu(screen, fonts)
        if mode is None:
            break

        if mode == "story":
            story.story_menu(screen, fonts)
            continue

        if mode in ("local", "easy", "medium", "hard"):
            ui.run_match(screen, fonts, mode, None, 1)
            continue

        if mode == "online":
            # Online match flow:
            # R = rematch on the existing connection/roles.
            # N = both return here, previous opponent preselected, roles may swap.
            # ESC = both leave online play and return to the main menu.
            while True:
                result = ui.online_lobby(screen, fonts)
                if result is None:
                    break
                online_mode, peer, local_player = result
                quick_next_match = ui.run_match(screen, fonts, online_mode, peer, local_player)
                if not quick_next_match:
                    break
            continue

        if mode == "nettest":
            preset = ui.network_test_menu(screen, fonts)
            if preset is not None:
                ui.run_network_test(screen, fonts, preset)

    pygame.quit()


if __name__ == "__main__":
    main()

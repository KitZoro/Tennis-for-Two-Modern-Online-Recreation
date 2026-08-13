from __future__ import annotations

import pygame

import ui
from audio import SoundManager
from config import AUDIO_SAMPLE_RATE, WIDTH, HEIGHT


def main() -> None:
    print("Starting Tennis for Two v27.2 Online Reliability + Network Test")
    pygame.mixer.pre_init(AUDIO_SAMPLE_RATE, -16, 1, 512)
    pygame.init()
    ui.SOUND = SoundManager()

    try:
        pygame.scrap.init()
    except pygame.error:
        pass

    pygame.display.set_caption("Tennis for Two — Secure Rollback v27.2 Network Test")
    ui._open_display(False)

    screen = pygame.Surface((WIDTH, HEIGHT)).convert()
    fonts = (
        pygame.font.SysFont("consolas", 42),
        pygame.font.SysFont("consolas", 27),
        pygame.font.SysFont("consolas", 17),
    )

    while True:
        mode = ui.menu(screen, fonts)
        if mode is None:
            break

        if mode in ("local", "easy", "medium", "hard"):
            ui.run_match(screen, fonts, mode, None, 1)
            continue

        if mode == "online":
            result = ui.online_lobby(screen, fonts)
            if result is not None:
                online_mode, peer, local_player = result
                ui.run_match(screen, fonts, online_mode, peer, local_player)
            continue

        if mode == "nettest":
            preset = ui.network_test_menu(screen, fonts)
            if preset is not None:
                ui.run_network_test(screen, fonts, preset)

    pygame.quit()


if __name__ == "__main__":
    main()

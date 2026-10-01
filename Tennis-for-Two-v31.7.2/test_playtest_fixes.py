"""Run with: python -m unittest -v test_playtest_fixes

Headless regression coverage for the September 2026 playtest fixes.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import math
import random
import unittest
from types import SimpleNamespace

from config import *
from cpu import CpuController
from game import initial_world, InputState, step_world, try_hit
from timing import offline_frame_dt


class PlaytestFixTests(unittest.TestCase):
    def test_shot_estimator_matches_fixed_step_integration(self):
        rng = random.Random(58120)
        for _ in range(1000):
            x0 = rng.uniform(NET_X + 20, RIGHT_EDGE)
            y0 = rng.uniform(GROUND_Y - 60, GROUND_Y - BALL_RADIUS)
            angle = rng.uniform(102, 170)
            speed = rng.uniform(230, 750)
            x, y = x0, y0
            vx = math.cos(math.radians(angle)) * speed
            vy = -math.sin(math.radians(angle)) * speed
            cleared = False
            for tick in range(1500):
                old_x = x
                vy += GRAVITY * FIXED_DT
                x += vx * FIXED_DT
                y += vy * FIXED_DT
                if old_x > NET_X >= x:
                    cleared = y + BALL_RADIUS <= GROUND_Y - NET_HEIGHT
                if y + BALL_RADIUS >= GROUND_Y and vy > 0:
                    break
            predicted, predicted_clear = CpuController.estimate_landing_x(x0, y0, angle, speed)
            self.assertAlmostEqual(predicted, x, places=7)
            self.assertEqual(predicted_clear, cleared)

    def test_planned_returns_land_legally_with_real_physics(self):
        for level in ("easy", "medium", "hard"):
            cpu = CpuController(level)
            for x in (550, 650, 750, 850):
                for y in (GROUND_Y-40, GROUND_Y-24, GROUND_Y-6):
                    for speed in (250, 400, 550):
                        for frame in (200, 431, 9999):
                            with self.subTest(level=level, x=x, y=y, speed=speed, frame=frame):
                                state = initial_world()
                                state.frame = frame
                                state.ball.attached = False
                                state.ball.last_hitter = 1
                                state.rally_active = True
                                state.p2.x = state.ball.x = x
                                state.ball.y = y
                                state.ball.vx, state.ball.vy = speed, 100
                                cpu.choose_shot(state)
                                state.p2.angle, state.p2.power = cpu.target_angle, cpu.target_power
                                try_hit(state, state.p2, 2)
                                self.assertEqual(state.ball.last_hitter, 2)
                                for _ in range(600):
                                    step_world(state, InputState(), InputState())
                                    if state.ball.bounces_on_side or state.score1 or state.score2:
                                        break
                                self.assertEqual(state.ball.bounce_side, 1, state.message)

    def test_easy_miss_is_not_rerolled_each_contact_tick(self):
        from unittest.mock import patch
        cpu = CpuController("easy")
        state = initial_world()
        state.ball.attached = False
        state.ball.last_hitter = 1
        state.ball.x = state.p2.x
        state.ball.y = GROUND_Y - 12
        state.ball.vx = 200
        with patch("cpu.random.random", return_value=0.0):
            self.assertFalse(cpu.update(state).hit)
        with patch("cpu.random.random", return_value=1.0):
            for _ in range(12):
                state.frame += 1
                self.assertFalse(cpu.update(state).hit)
            state.ball.last_hitter = 2
            cpu.update(state)
            state.ball.last_hitter = 1
            self.assertTrue(cpu.update(state).hit)

    def test_serves_use_real_attached_ball_position(self):
        for level in ("easy", "medium", "hard"):
            from game import reset_round
            state = initial_world()
            reset_round(state, 2)
            cpu = CpuController(level)
            for _ in range(1000):
                step_world(state, InputState(), cpu.update(state))
                if state.ball.bounces_on_side or state.score1 or state.score2:
                    break
            self.assertEqual(state.ball.bounce_side, 1, (level, state.message))

    def test_low_render_rates_preserve_simulation_speed(self):
        for render_fps in (120, 60, 30, 15, 10):
            state = initial_world()
            accumulator = 0.0
            for frame in range(render_fps * 2):
                accumulator += offline_frame_dt(1000 / render_fps)
                while accumulator >= FIXED_DT:
                    step_world(state, InputState(), InputState())
                    accumulator -= FIXED_DT
            self.assertLessEqual(abs(state.frame - 240), 1, render_fps)
        self.assertEqual(offline_frame_dt(5000), .25)

    def test_each_story_chapter_keeps_time_at_15_fps(self):
        import pygame
        import story
        from unittest.mock import patch
        for chapter in story.CHAPTERS:
            ticks = []
            event_calls = [0]
            def events():
                event_calls[0] += 1
                return [pygame.event.Event(pygame.QUIT)] if event_calls[0] > 30 else []
            def step(state, p1, p2):
                step_world(state, p1, p2)
                ticks.append(state.frame)
            clock = SimpleNamespace(tick=lambda fps: 1000 / 15)
            with patch.object(story.pygame.time, "Clock", return_value=clock), \
                 patch.object(story.ui, "game_events", side_effect=events), \
                 patch.object(story.ui, "keyboard_input_for", return_value=InputState()), \
                 patch.object(story.ui, "draw_game"), \
                 patch.object(story.ui, "draw_text"), \
                 patch.object(story.ui, "present"), \
                 patch.object(story, "step_world", side_effect=step):
                self.assertIsNone(story._play_challenge(None, (None, None, None), chapter))
            self.assertLessEqual(abs(len(ticks) - 240), 1, chapter.title)

    def test_ground_covers_legal_edges(self):
        import pygame
        import ui
        pygame.init()
        screen = pygame.Surface((WIDTH, HEIGHT))
        fonts = tuple(pygame.font.Font(None, size) for size in (48, 26, 18))
        state = initial_world()
        # Keep players away from the edge pixels being checked.
        from rollback import RollbackSession
        session = RollbackSession(1, None, is_host=True)
        try:
            session.state = state
            ui.draw_game(screen, session, fonts, "TEST")
            for x in (LEFT_EDGE, LEFT_EDGE + 10, RIGHT_EDGE - 10, RIGHT_EDGE):
                self.assertEqual(tuple(screen.get_at((x, GROUND_Y)))[:3], GREEN)
        finally:
            session.close()
            pygame.quit()


if __name__ == "__main__":
    unittest.main()

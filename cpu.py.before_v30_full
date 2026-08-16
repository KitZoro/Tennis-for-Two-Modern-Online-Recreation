from __future__ import annotations

import math
import random
from dataclasses import asdict

from config import *
from game import BallState, InputState, WorldState, clamp


class CpuController:
    """Predictive CPU with distinct behavior at each difficulty."""

    def __init__(self, difficulty: str):
        self.difficulty = difficulty
        self.target_x = RIGHT_EDGE - 135
        self.target_angle = 137.0
        self.target_power = POWER_DEFAULT
        self.last_plan_frame = -999

    @staticmethod
    def predict_intercept_x(state: WorldState) -> float:
        """Simulate the incoming ball and estimate its low descending position."""
        ball = BallState(**asdict(state.ball))
        if ball.attached or ball.vx <= 0:
            return RIGHT_EDGE - 135

        dt = 1.0 / 120.0
        best_x = ball.x

        for _ in range(480):
            previous_x = ball.x
            ball.vy += GRAVITY * dt
            ball.x += ball.vx * dt
            ball.y += ball.vy * dt

            # Approximate the same net collision used by the real simulation.
            net_top = GROUND_Y - NET_HEIGHT
            crossed_net = (previous_x < NET_X <= ball.x) or (previous_x > NET_X >= ball.x)
            if crossed_net and ball.y + BALL_RADIUS > net_top:
                if ball.vx > 0:
                    ball.x = NET_X - BALL_RADIUS - 4
                    ball.vx = -abs(ball.vx) * 0.58
                else:
                    ball.x = NET_X + BALL_RADIUS + 4
                    ball.vx = abs(ball.vx) * 0.58
                ball.vy *= 0.75

            if ball.x > NET_X and ball.vy > 0:
                best_x = ball.x
                if ball.y >= GROUND_Y - 24:
                    break

            if ball.x < 0 or ball.x > WIDTH:
                break

        return clamp(best_x, NET_X + 36, RIGHT_EDGE)

    @staticmethod
    def estimate_landing_x(
        start_x: float,
        start_y: float,
        angle: float,
        speed: float,
    ) -> tuple[float, bool]:
        """Return estimated first landing X and whether the shot clears the net."""
        radians = math.radians(angle)
        x = start_x
        y = start_y
        vx = math.cos(radians) * speed
        vy = -math.sin(radians) * speed
        dt = 1.0 / 180.0
        cleared_net = False
        previous_x = x

        for _ in range(900):
            previous_x = x
            vy += GRAVITY * dt
            x += vx * dt
            y += vy * dt

            if previous_x > NET_X >= x:
                if y + BALL_RADIUS <= GROUND_Y - NET_HEIGHT:
                    cleared_net = True
                else:
                    return x, False

            if y + BALL_RADIUS >= GROUND_Y and vy > 0:
                return x, cleared_net

            if x < -100 or x > WIDTH + 100:
                break

        return x, cleared_net

    def choose_shot(self, state: WorldState) -> None:
        """Search angle/power combinations and aim where Player 1 is not."""
        # Aim for the side farthest from Player 1.
        if state.p1.x < (LEFT_EDGE + NET_X) / 2:
            desired_x = NET_X - 55
        else:
            desired_x = LEFT_EDGE + 35

        if self.difficulty == "easy":
            # Still strategic, but explores fewer combinations and avoids extreme power.
            powers = (75, 85, 95, 105)
            angles = range(114, 160, 5)
        elif self.difficulty == "medium":
            powers = (80, 90, 100, 110, 120)
            angles = range(108, 166, 3)
        else:
            powers = (90, 100, 110, 120, 130, 140)
            angles = range(102, 170, 2)

        incoming = math.hypot(state.ball.vx, state.ball.vy)
        best_score = float("inf")
        best_angle = 137.0
        best_power = POWER_DEFAULT

        for power in powers:
            factor = power / 100.0
            if state.ball.attached:
                speed = SERVE_SPEED * factor
            else:
                base_speed = max(RETURN_SPEED, incoming * 1.04)
                speed = clamp(base_speed * factor, 225.0, MAX_BALL_SPEED * 1.18)

            for angle in angles:
                landing_x, cleared = self.estimate_landing_x(
                    state.p2.x,
                    GROUND_Y - 12,
                    float(angle),
                    speed,
                )
                if not cleared:
                    continue

                # Reward landing in bounds and far from Player 1.
                out_penalty = 0.0
                if landing_x < LEFT_EDGE:
                    out_penalty += (LEFT_EDGE - landing_x) * 8.0
                elif landing_x > NET_X - 12:
                    out_penalty += (landing_x - (NET_X - 12)) * 8.0

                distance_from_target = abs(landing_x - desired_x)
                distance_from_player = abs(landing_x - state.p1.x)
                score = distance_from_target + out_penalty - distance_from_player * 0.18

                # Hard favors pressure without using reckless maximum power.
                if self.difficulty == "hard":
                    score -= power * 0.08

                if score < best_score:
                    best_score = score
                    best_angle = float(angle)
                    best_power = int(power)

        self.target_angle = best_angle
        self.target_power = best_power

    def update(self, state: WorldState) -> InputState:
        settings = {
            # Every level predicts the ball, chooses power, and aims strategically.
            # The differences are reaction speed, placement accuracy, and timing.
            "easy": {
                "reaction": 12,
                "position_error": 38.0,
                "move_skip": 0.14,
                "miss": 0.08,
                "hit_margin": 0.95,
            },
            "medium": {
                "reaction": 4,
                "position_error": 12.0,
                "move_skip": 0.025,
                "miss": 0.015,
                "hit_margin": 1.08,
            },
            "hard": {
                "reaction": 1,
                "position_error": 0.0,
                "move_skip": 0.0,
                "miss": 0.0,
                "hit_margin": 1.18,
            },
        }[self.difficulty]

        ball = state.ball

        if state.frame - self.last_plan_frame >= settings["reaction"]:
            self.last_plan_frame = state.frame

            if ball.attached and ball.server == 2:
                self.target_x = state.p2.x
                self.choose_shot(state)
            elif ball.vx > 0:
                predicted = self.predict_intercept_x(state)
                error = settings["position_error"]
                if error:
                    predicted += random.uniform(-error, error)
                self.target_x = clamp(predicted, NET_X + 36, RIGHT_EDGE)
                self.choose_shot(state)
            else:
                # Every difficulty recovers to a defensive position and prepares
                # its next shot. Hard updates this most often because of reaction speed.
                self.target_x = RIGHT_EDGE - 155
                self.choose_shot(state)

        left = state.p2.x > self.target_x + 3
        right = state.p2.x < self.target_x - 3

        if settings["move_skip"] and random.random() < settings["move_skip"]:
            left = right = False

        angle_up = state.p2.angle > self.target_angle + 0.5
        angle_down = state.p2.angle < self.target_angle - 0.5

        power_down = state.p2.power > self.target_power
        power_up = state.p2.power < self.target_power

        # Account for the selected power's actual contact window.
        if state.p2.power <= 80:
            contact_range = HIT_RANGE + 8.0
        elif state.p2.power <= 100:
            contact_range = HIT_RANGE
        else:
            contact_range = max(27.0, HIT_RANGE - (state.p2.power - 100) * 0.30)

        contact_range *= settings["hit_margin"]
        near = math.hypot(
            ball.x - state.p2.x,
            ball.y - (GROUND_Y - 12),
        ) <= contact_range

        hit = False
        if ball.attached and ball.server == 2:
            # Respect the same serve guard as a human: wait 1/4 second and
            # supply a released frame before making a fresh serve press.
            if state.serve_delay_frames > 0 or not state.serve_release_seen:
                hit = False
            else:
                ready_angle = abs(state.p2.angle - self.target_angle) <= 2.0
                ready_power = abs(state.p2.power - self.target_power) <= POWER_STEP
                hit = ready_angle and ready_power
        elif near and ball.last_hitter != 2:
            hit = random.random() >= settings["miss"]

        return InputState(
            left=left,
            right=right,
            angle_up=angle_up,
            angle_down=angle_down,
            power_down=power_down,
            power_up=power_up,
            hit=hit,
        )


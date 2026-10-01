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
        self.last_shot = None
        self.miss_return = False

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
        # Closed-form version of the game's semi-implicit 120 Hz integration:
        # y(n) = y0 + n*vy*dt + gravity*dt^2*n*(n+1)/2.
        # Use the first integer tick at each crossing, not a continuous parabola
        # or the old 180 Hz approximation. No per-candidate simulation loop.
        radians = math.radians(angle)
        vx = math.cos(radians) * speed
        vy = -math.sin(radians) * speed
        a = 0.5 * GRAVITY * FIXED_DT * FIXED_DT
        b = vy * FIXED_DT + a
        c = start_y + BALL_RADIUS - GROUND_Y
        discriminant = b * b - 4.0 * a * c
        if discriminant < 0 or vx >= 0:
            return start_x, False
        landing_tick = max(1, math.ceil((-b + math.sqrt(discriminant)) / (2.0 * a)))
        landing_x = start_x + vx * FIXED_DT * landing_tick
        if start_x <= NET_X:
            return landing_x, False
        net_tick = max(1, math.ceil((NET_X - start_x) / (vx * FIXED_DT)))
        net_y = start_y + net_tick * vy * FIXED_DT + a * net_tick * (net_tick + 1)
        cleared = net_tick <= landing_tick and net_y + BALL_RADIUS <= GROUND_Y - NET_HEIGHT
        return landing_x, cleared

    def choose_shot(self, state: WorldState) -> None:
        """Search angle/power combinations and aim where Player 1 is not."""
        # Easy teaches rallies; later opponents place shots away from the
        # player, with medium keeping a larger safety margin than hard.
        if self.difficulty == "easy":
            desired_x = (LEFT_EDGE + NET_X) / 2
            powers = (60, 70, 80, 90, 100, 110, 120)
            angles = range(112, 169, 4)
        elif self.difficulty == "medium":
            desired_x = NET_X - 100 if state.p1.x < (LEFT_EDGE + NET_X) / 2 else LEFT_EDGE + 100
            powers = (60, 70, 80, 90, 100, 110, 120)
            angles = range(108, 169, 3)
        else:
            desired_x = NET_X - 55 if state.p1.x < (LEFT_EDGE + NET_X) / 2 else LEFT_EDGE + 55
            powers = (60, 70, 80, 90, 100, 110, 120, 130)
            angles = range(102, 171, 2)

        ball = state.ball
        incoming = math.hypot(ball.vx, ball.vy)
        if ball.attached:
            # A serve launches from the attached ball, not the player's feet.
            start_x, start_y = state.p2.x - 18, GROUND_Y - 18
        elif math.hypot(ball.x - state.p2.x, ball.y - (GROUND_Y - 12)) <= HIT_RANGE + 18:
            start_x, start_y = ball.x, ball.y
        else:
            # Plan for where contact will happen, rather than where the CPU
            # stands while it is still running towards the incoming ball.
            start_x = self.target_x
            start_y = GROUND_Y - 24
            incoming = math.sqrt(max(0.0, incoming * incoming + 2 * GRAVITY * (start_y - ball.y)))
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
                    start_x,
                    start_y,
                    float(angle),
                    speed,
                )
                if not cleared:
                    continue
                # High power adds angle scatter in the real game. Reject shots
                # that only clear the net at the nominal (perfect) angle.
                spread = max(0, power - 100) * 0.125
                if spread:
                    low_x, low_clear = self.estimate_landing_x(start_x, start_y, angle - spread, speed)
                    high_x, high_clear = self.estimate_landing_x(start_x, start_y, angle + spread, speed)
                    if not (low_clear and high_clear):
                        continue
                    if min(low_x, high_x) < LEFT_EDGE + 8 or max(low_x, high_x) > NET_X - 12:
                        continue

                # Reward landing in bounds and far from Player 1.
                out_penalty = 0.0
                if landing_x < LEFT_EDGE:
                    out_penalty += (LEFT_EDGE - landing_x) * 8.0
                elif landing_x > NET_X - 12:
                    out_penalty += (landing_x - (NET_X - 12)) * 8.0

                distance_from_target = abs(landing_x - desired_x)
                distance_from_player = abs(landing_x - state.p1.x)
                pressure = 0.0 if self.difficulty == "easy" else 0.18
                score = distance_from_target + out_penalty - distance_from_player * pressure
                # Prefer controllable shots when placement is otherwise similar.
                score += max(0, power - 100) * 0.25

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
                "reaction": 24,
                "position_error": 38.0,
                "move_skip": 0.14,
                "miss": 0.18,
                "hit_margin": 0.95,
            },
            "medium": {
                "reaction": 8,
                "position_error": 12.0,
                "move_skip": 0.025,
                "miss": 0.04,
                "hit_margin": 1.08,
            },
            "hard": {
                "reaction": 2,
                "position_error": 0.0,
                "move_skip": 0.0,
                "miss": 0.0,
                "hit_margin": 1.18,
            },
        }[self.difficulty]

        ball = state.ball
        shot = (state.rally_id, ball.last_hitter)
        if shot != self.last_shot:
            self.last_shot = shot
            # Sample once per incoming return. Re-rolling every 120 Hz tick
            # made the old easy miss chance effectively disappear.
            self.miss_return = (
                not ball.attached and ball.last_hitter == 1
                and settings["miss"] > 0 and random.random() < settings["miss"]
            )

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
                # Retain the shot while the ball travels away; there is no
                # incoming contact to plan yet.

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
            hit = not self.miss_return

        return InputState(
            left=left,
            right=right,
            angle_up=angle_up,
            angle_down=angle_down,
            power_down=power_down,
            power_up=power_up,
            hit=hit,
        )


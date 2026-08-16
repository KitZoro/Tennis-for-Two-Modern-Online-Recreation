from __future__ import annotations

from config import *
from game import InputState, WorldState, clamp
from cpu import CpuController


class DeterministicTestCpu:
    """Deterministic CPU used only by the one-PC v28 network test."""

    def __init__(self):
        self.target_x = RIGHT_EDGE - 135
        self.target_angle = 137.0
        self.target_power = 75
        self.last_plan_frame = -999

    def update(self, state: WorldState) -> InputState:
        ball = state.ball

        # Same ~30 Hz planning cadence as the prior 60 Hz/2-frame test CPU.
        if state.frame - self.last_plan_frame >= 4:
            self.last_plan_frame = state.frame
            if ball.attached and ball.server == 2:
                self.target_x = state.p2.x
            elif ball.vx > 0:
                self.target_x = clamp(
                    CpuController.predict_intercept_x(state),
                    NET_X + 36,
                    RIGHT_EDGE,
                )
            else:
                self.target_x = RIGHT_EDGE - 155

        left = state.p2.x > self.target_x + 2
        right = state.p2.x < self.target_x - 2

        angle_up = state.p2.angle > self.target_angle + 0.5
        angle_down = state.p2.angle < self.target_angle - 0.5
        power_down = state.p2.power > self.target_power
        power_up = state.p2.power < self.target_power

        hit = False
        if ball.attached and ball.server == 2:
            if state.serve_delay_frames <= 0 and state.serve_release_seen:
                ready_angle = abs(state.p2.angle - self.target_angle) <= 2.0
                ready_power = abs(state.p2.power - self.target_power) <= POWER_STEP
                hit = ready_angle and ready_power
        elif ball.vx > 0 and ball.last_hitter != 2:
            hit = True

        return InputState(
            left=left,
            right=right,
            angle_up=angle_up,
            angle_down=angle_down,
            power_down=power_down,
            power_up=power_up,
            hit=hit,
        )

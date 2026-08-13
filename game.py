from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Optional

from config import *


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class InputState:
    left: bool = False
    right: bool = False
    angle_up: bool = False
    angle_down: bool = False
    power_down: bool = False
    power_up: bool = False
    hit: bool = False

    def packed(self) -> int:
        return (
            int(self.left)
            | (int(self.right) << 1)
            | (int(self.angle_up) << 2)
            | (int(self.angle_down) << 3)
            | (int(self.hit) << 4)
            | (int(self.power_down) << 5)
            | (int(self.power_up) << 6)
        )

    @classmethod
    def unpacked(cls, value: int) -> "InputState":
        value = int(value) & 0x7F
        return cls(
            left=bool(value & 1),
            right=bool(value & 2),
            angle_up=bool(value & 4),
            angle_down=bool(value & 8),
            hit=bool(value & 16),
            power_down=bool(value & 32),
            power_up=bool(value & 64),
        )


NEUTRAL_INPUT = InputState()


@dataclass
class PlayerState:
    x: float
    angle: float
    cooldown_frames: int = 0
    power: int = POWER_DEFAULT
    power_repeat_frames: int = 0


@dataclass
class BallState:
    x: float
    y: float
    vx: float
    vy: float
    server: int
    attached: bool
    last_hitter: int
    bounce_side: int
    bounces_on_side: int


@dataclass
class WorldState:
    frame: int
    p1: PlayerState
    p2: PlayerState
    ball: BallState
    score1: int
    score2: int
    server: int
    winner: int
    message: str
    rally_id: int
    rally_active: bool
    serve_delay_frames: int
    serve_release_seen: bool

    def clone(self) -> "WorldState":
        return WorldState(
            frame=self.frame,
            p1=PlayerState(**asdict(self.p1)),
            p2=PlayerState(**asdict(self.p2)),
            ball=BallState(**asdict(self.ball)),
            score1=self.score1,
            score2=self.score2,
            server=self.server,
            winner=self.winner,
            message=self.message,
            rally_id=self.rally_id,
            rally_active=self.rally_active,
            serve_delay_frames=self.serve_delay_frames,
            serve_release_seen=self.serve_release_seen,
        )

    def canonical_dict(self) -> dict:
        # Round floats before hashing/transport to minimize platform noise.
        def r(v: float) -> float:
            return round(float(v), 6)

        return {
            "frame": self.frame,
            "p1": {
                "x": r(self.p1.x),
                "angle": r(self.p1.angle),
                "cooldown_frames": self.p1.cooldown_frames,
                "power": self.p1.power,
                "power_repeat_frames": self.p1.power_repeat_frames,
            },
            "p2": {
                "x": r(self.p2.x),
                "angle": r(self.p2.angle),
                "cooldown_frames": self.p2.cooldown_frames,
                "power": self.p2.power,
                "power_repeat_frames": self.p2.power_repeat_frames,
            },
            "ball": {
                "x": r(self.ball.x), "y": r(self.ball.y),
                "vx": r(self.ball.vx), "vy": r(self.ball.vy),
                "server": self.ball.server, "attached": self.ball.attached,
                "last_hitter": self.ball.last_hitter,
                "bounce_side": self.ball.bounce_side,
                "bounces_on_side": self.ball.bounces_on_side,
            },
            "score1": self.score1,
            "score2": self.score2,
            "server": self.server,
            "winner": self.winner,
            "message": self.message[:80],
            "rally_id": self.rally_id,
            "rally_active": self.rally_active,
            "serve_delay_frames": self.serve_delay_frames,
            "serve_release_seen": self.serve_release_seen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        return cls(
            frame=int(data["frame"]),
            p1=PlayerState(
                x=float(data["p1"]["x"]),
                angle=float(data["p1"]["angle"]),
                cooldown_frames=int(data["p1"]["cooldown_frames"]),
                power=int(data["p1"].get("power", POWER_DEFAULT)),
                power_repeat_frames=int(data["p1"].get("power_repeat_frames", 0)),
            ),
            p2=PlayerState(
                x=float(data["p2"]["x"]),
                angle=float(data["p2"]["angle"]),
                cooldown_frames=int(data["p2"]["cooldown_frames"]),
                power=int(data["p2"].get("power", POWER_DEFAULT)),
                power_repeat_frames=int(data["p2"].get("power_repeat_frames", 0)),
            ),
            ball=BallState(
                x=float(data["ball"]["x"]),
                y=float(data["ball"]["y"]),
                vx=float(data["ball"]["vx"]),
                vy=float(data["ball"]["vy"]),
                server=int(data["ball"]["server"]),
                attached=bool(data["ball"]["attached"]),
                last_hitter=int(data["ball"]["last_hitter"]),
                bounce_side=int(data["ball"]["bounce_side"]),
                bounces_on_side=int(data["ball"]["bounces_on_side"]),
            ),
            score1=int(data["score1"]),
            score2=int(data["score2"]),
            server=int(data["server"]),
            winner=int(data["winner"]),
            message=str(data["message"])[:80],
            rally_id=int(data.get("rally_id", 0)),
            rally_active=bool(data.get("rally_active", not bool(data["ball"]["attached"]))),
            serve_delay_frames=int(data.get("serve_delay_frames", 0)),
            serve_release_seen=bool(data.get("serve_release_seen", True)),
        )



@dataclass
class RenderState:
    """Visual-only positions that soften rollback corrections.

    Gameplay always uses WorldState. This layer never changes collision,
    scoring, or hit detection; it only prevents corrected positions from
    teleporting across the screen in one rendered frame.
    """
    p1_x: float
    p2_x: float
    ball_x: float
    ball_y: float

    @classmethod
    def from_world(cls, state: WorldState) -> "RenderState":
        return cls(
            p1_x=state.p1.x,
            p2_x=state.p2.x,
            ball_x=state.ball.x,
            ball_y=state.ball.y,
        )

    @staticmethod
    def _approach(current: float, target: float, amount: float) -> float:
        return current + (target - current) * amount

    def update(self, state: WorldState, local_player: Optional[int] = None) -> None:
        # Keep the local player's own paddle exact so controls never feel mushy.
        if local_player == 1:
            self.p1_x = state.p1.x
        else:
            if abs(state.p1.x - self.p1_x) > RENDER_SNAP_DISTANCE:
                self.p1_x = state.p1.x
            else:
                self.p1_x = self._approach(self.p1_x, state.p1.x, RENDER_SMOOTHING)

        if local_player == 2:
            self.p2_x = state.p2.x
        else:
            if abs(state.p2.x - self.p2_x) > RENDER_SNAP_DISTANCE:
                self.p2_x = state.p2.x
            else:
                self.p2_x = self._approach(self.p2_x, state.p2.x, RENDER_SMOOTHING)

        ball_distance = math.hypot(state.ball.x - self.ball_x, state.ball.y - self.ball_y)
        if state.ball.attached or ball_distance > RENDER_BALL_SNAP_DISTANCE:
            self.ball_x = state.ball.x
            self.ball_y = state.ball.y
        else:
            # The ball catches up quickly enough to remain useful for timing,
            # but no longer teleports on every rollback correction.
            self.ball_x = self._approach(self.ball_x, state.ball.x, 0.52)
            self.ball_y = self._approach(self.ball_y, state.ball.y, 0.52)


def initial_world() -> WorldState:
    p1 = PlayerState(LEFT_EDGE + 135, 43.0)
    p2 = PlayerState(RIGHT_EDGE - 135, 137.0)
    ball = BallState(
        x=p1.x + 18,
        y=GROUND_Y - 18,
        vx=0.0,
        vy=0.0,
        server=1,
        attached=True,
        last_hitter=0,
        bounce_side=0,
        bounces_on_side=0,
    )
    return WorldState(
        frame=0,
        p1=p1,
        p2=p2,
        ball=ball,
        score1=0,
        score2=0,
        server=1,
        winner=0,
        message="PLAYER 1 READY",
        rally_id=1,
        rally_active=False,
        serve_delay_frames=SERVE_DELAY_FRAMES,
        serve_release_seen=False,
    )


def reset_round(state: WorldState, server: int) -> None:
    """Start a completely clean rally with a 1/4-second serve guard."""
    state.server = server
    state.rally_id += 1
    state.rally_active = False
    state.serve_delay_frames = SERVE_DELAY_FRAMES
    state.serve_release_seen = False

    # Recreate both players so cooldown/repeat state from the previous rally
    # cannot leak into the next point.
    state.p1 = PlayerState(LEFT_EDGE + 135, 43.0)
    state.p2 = PlayerState(RIGHT_EDGE - 135, 137.0)

    owner = state.p1 if server == 1 else state.p2
    state.ball = BallState(
        x=owner.x + (18 if server == 1 else -18),
        y=GROUND_Y - 18,
        vx=0.0,
        vy=0.0,
        server=server,
        attached=True,
        last_hitter=0,
        bounce_side=0,
        bounces_on_side=0,
    )
    state.message = f"PLAYER {server} READY"


def award_point(state: WorldState, player: int, reason: str = "") -> None:
    # A point can only be awarded while a served rally is live. This prevents
    # stale collision/bounce state from an old rally from scoring into a fresh one.
    if state.winner or not state.rally_active:
        return
    if player == 1:
        state.score1 += 1
    else:
        state.score2 += 1

    if max(state.score1, state.score2) >= WIN_SCORE and abs(state.score1 - state.score2) >= WIN_BY:
        state.winner = 1 if state.score1 > state.score2 else 2
        state.message = f"PLAYER {state.winner} WINS — PRESS R"
        state.rally_active = False
        state.ball.attached = True
        state.ball.vx = state.ball.vy = 0.0
    else:
        reset_round(state, player)
        if reason:
            state.message = f"{reason} — PLAYER {player} SCORES"


def update_player(player: PlayerState, side: int, inp: InputState) -> None:
    move = float(inp.right) - float(inp.left)
    player.x += move * PLAYER_SPEED * FIXED_DT

    if side == 1:
        if inp.angle_up:
            player.angle += ANGLE_SPEED * FIXED_DT
        if inp.angle_down:
            player.angle -= ANGLE_SPEED * FIXED_DT
        player.angle = clamp(player.angle, 10.0, 80.0)
        player.x = clamp(player.x, LEFT_EDGE, NET_X - 34)
    else:
        if inp.angle_up:
            player.angle -= ANGLE_SPEED * FIXED_DT
        if inp.angle_down:
            player.angle += ANGLE_SPEED * FIXED_DT
        player.angle = clamp(player.angle, 100.0, 170.0)
        player.x = clamp(player.x, NET_X + 34, RIGHT_EDGE)

    player.cooldown_frames = max(0, player.cooldown_frames - 1)

    player.power_repeat_frames = max(0, player.power_repeat_frames - 1)
    if player.power_repeat_frames == 0:
        if inp.power_down and not inp.power_up:
            player.power = max(POWER_MIN, player.power - POWER_STEP)
            player.power_repeat_frames = POWER_CHANGE_REPEAT
        elif inp.power_up and not inp.power_down:
            player.power = min(POWER_MAX, player.power + POWER_STEP)
            player.power_repeat_frames = POWER_CHANGE_REPEAT


def deterministic_shot_error(state: WorldState, side: int, power: int) -> float:
    if power <= 100:
        return 0.0
    error_range = (power - 100) * 0.125
    seed = (
        state.frame * 1103515245
        + side * 12345
        + state.score1 * 97
        + state.score2 * 193
    ) & 0x7FFFFFFF
    normalized = ((seed % 2001) / 1000.0) - 1.0
    return normalized * error_range


def try_hit(state: WorldState, player: PlayerState, side: int) -> None:
    if player.cooldown_frames > 0 or state.winner:
        return

    ball = state.ball
    power_factor = player.power / 100.0

    if player.power <= 80:
        effective_hit_range = HIT_RANGE + 8.0
    elif player.power <= 100:
        effective_hit_range = HIT_RANGE
    else:
        effective_hit_range = max(27.0, HIT_RANGE - (player.power - 100) * 0.30)

    if ball.attached:
        if ball.server != side:
            return
        if state.serve_delay_frames > 0 or not state.serve_release_seen:
            return
        speed = SERVE_SPEED * power_factor
    else:
        if ball.last_hitter == side:
            return
        distance = math.hypot(ball.x - player.x, ball.y - (GROUND_Y - 12))
        if distance > effective_hit_range:
            return
        incoming = math.hypot(ball.vx, ball.vy)
        base_speed = max(RETURN_SPEED, incoming * 1.04)
        speed = clamp(base_speed * power_factor, 225.0, MAX_BALL_SPEED * 1.18)

    shot_angle = player.angle + deterministic_shot_error(state, side, player.power)
    if side == 1:
        shot_angle = clamp(shot_angle, 7.0, 83.0)
    else:
        shot_angle = clamp(shot_angle, 97.0, 173.0)

    radians = math.radians(shot_angle)
    ball.vx = math.cos(radians) * speed
    ball.vy = -math.sin(radians) * speed
    ball.attached = False
    ball.last_hitter = side
    ball.bounce_side = 0
    ball.bounces_on_side = 0

    extra_recovery = max(0, (player.power - 100) // 10)
    player.cooldown_frames = HIT_COOLDOWN_FRAMES + extra_recovery
    if not state.rally_active:
        state.rally_active = True
    state.message = f"RALLY — P{side} POWER {player.power}%"


def step_world(state: WorldState, p1_input: InputState, p2_input: InputState) -> None:
    if state.winner:
        state.frame += 1
        return

    update_player(state.p1, 1, p1_input)
    update_player(state.p2, 2, p2_input)

    ball = state.ball

    # New-point transition:
    # 1) wait exactly 1/4 second,
    # 2) require the server's hit button to be released at least once,
    # 3) only a fresh press can serve.
    #
    # Movement, angle and power remain adjustable during the delay.
    if ball.attached:
        owner = state.p1 if ball.server == 1 else state.p2
        ball.x = owner.x + (18 if ball.server == 1 else -18)
        ball.y = GROUND_Y - 18

        server_input = p1_input if ball.server == 1 else p2_input
        server_player = state.p1 if ball.server == 1 else state.p2

        if state.serve_delay_frames > 0:
            state.serve_delay_frames -= 1
            remaining = state.serve_delay_frames / FPS
            state.message = f"PLAYER {ball.server} READY — {remaining:.2f}s"
            state.frame += 1
            return

        if not state.serve_release_seen:
            if server_input.hit:
                state.message = f"PLAYER {ball.server} READY — RELEASE HIT"
                state.frame += 1
                return
            state.serve_release_seen = True
            state.message = f"PLAYER {ball.server} SERVE"
            state.frame += 1
            return

        if server_input.hit:
            try_hit(state, server_player, ball.server)

        # Still attached means the player has not made a fresh serve press yet.
        if ball.attached:
            state.message = f"PLAYER {ball.server} SERVE"
            state.frame += 1
            return

    # Once the serve is live, normal rally hits are processed.
    if p1_input.hit:
        try_hit(state, state.p1, 1)
    if p2_input.hit:
        try_hit(state, state.p2, 2)

    previous_x = ball.x
    ball.vy += GRAVITY * FIXED_DT
    ball.x += ball.vx * FIXED_DT
    ball.y += ball.vy * FIXED_DT

    net_top = GROUND_Y - NET_HEIGHT
    crossed_net = (previous_x < NET_X <= ball.x) or (previous_x > NET_X >= ball.x)
    if crossed_net and ball.y + BALL_RADIUS > net_top:
        # A shot into the net immediately loses the rally.
        hitter = ball.last_hitter
        award_point(
            state,
            2 if hitter == 1 else 1,
            f"PLAYER {hitter} HIT THE NET",
        )
        state.frame += 1
        return

    if ball.y + BALL_RADIUS >= GROUND_Y:
        ball.y = GROUND_Y - BALL_RADIUS

        # A first landing beyond the lines is out. However, if the ball already
        # bounced legally in bounds and only then travels outside the court,
        # the hitter wins when it reaches the ground again because the receiver
        # failed to return it.
        if ball.x < LEFT_EDGE or ball.x > RIGHT_EDGE:
            hitter = ball.last_hitter
            if ball.bounces_on_side > 0:
                receiver = 2 if hitter == 1 else 1
                award_point(
                    state,
                    hitter,
                    f"PLAYER {receiver} MISSED AFTER THE BOUNCE",
                )
            else:
                award_point(
                    state,
                    2 if hitter == 1 else 1,
                    f"PLAYER {hitter} HIT OUT",
                )
            state.frame += 1
            return

        side = 1 if ball.x < NET_X else 2

        # A legal return must land on the opponent's side.
        if ball.last_hitter == side:
            award_point(
                state,
                2 if ball.last_hitter == 1 else 1,
                f"PLAYER {ball.last_hitter} HIT THE WRONG SIDE",
            )
            state.frame += 1
            return

        if side == ball.bounce_side:
            ball.bounces_on_side += 1
        else:
            ball.bounce_side = side
            ball.bounces_on_side = 1

        ball.vy = -abs(ball.vy) * 0.72
        ball.vx *= 0.96

        if ball.bounces_on_side >= 2:
            scorer = 2 if side == 1 else 1
            award_point(
                state,
                scorer,
                f"PLAYER {side} MISSED THE RETURN",
            )
            state.frame += 1
            return

    # Before the first legal bounce, flying far beyond the court is out.
    # After a legal bounce, the receiver may still chase and return the ball
    # outside the court, so crossing the edge alone must not end the point.
    if ball.bounces_on_side == 0 and (
        ball.x < LEFT_EDGE - 40 or ball.x > RIGHT_EDGE + 40
    ):
        hitter = ball.last_hitter
        award_point(
            state,
            2 if hitter == 1 else 1,
            f"PLAYER {hitter} HIT OUT",
        )
        state.frame += 1
        return

    state.frame += 1


def state_hash(state: WorldState) -> str:
    raw = json.dumps(state.canonical_dict(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]

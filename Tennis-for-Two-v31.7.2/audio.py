from __future__ import annotations

import array
import json # added
import math
import time
from pathlib import Path
from typing import Optional

import pygame

from config import AUDIO_SAMPLE_RATE, AUDIO_VOLUME, MUSIC_VOLUME, CONFIG_DIR # added CONFIG_DIR here
from game import WorldState

AUDIO_SAVE = CONFIG_DIR / "audio_settings.json" # added
BUILT_IN_MUSIC = "BUILT-IN SYNTH"
SUPPORTED_MUSIC_SUFFIXES = {".ogg", ".mp3", ".wav"}
MAX_USER_VOLUME = 2.0
VOLUME_STEP = 0.10
# Calibrates the generated synth to roughly the same perceived level as the
# external tracks after their -14 LUFS normalization.
BUILT_IN_TRACK_GAIN = 0.55

class SoundManager:
    """Sound effects plus either custom streamed music or a synthesized fallback.

    Put a supported file in the project's music/ folder. Files named gameplay.ogg,
    gameplay.mp3, or gameplay.wav are preferred; otherwise the first supported
    audio file alphabetically is used.
    """

    def __init__(self) -> None:
        self.enabled = False
        self.sfx_muted = False
        self.music_muted = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music_channel: Optional[pygame.mixer.Channel] = None
        self.music_path: Optional[Path] = None
        # None preserves the older "pick the first file" behavior until the
        # player explicitly chooses a track.  Afterwards the filename (or the
        # built-in synth label) is saved in audio_settings.json.
        self.selected_music: Optional[str] = None
        self.using_streamed_music = False
        self._last_level_apply = 0.0
        self._seen_events: set[tuple] = set()
        self._seen_order: list[tuple] = []

        # My addition, holds the % of the volume the user wants.
        self.sfx_volume = 1.0 # sound
        self.music_volume = 1.0 # music
        self._load_volume_settings()

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(
                    frequency=AUDIO_SAMPLE_RATE,
                    size=-16,
                    channels=1,
                    buffer=512,
                )
            self.sounds = {
                "hit": self._tone(760, 0.055, 0.55, "square", 0.015),
                "serve": self._tone(620, 0.075, 0.60, "triangle", 0.020),
                "bounce": self._tone(185, 0.045, 0.38, "sine", 0.012),
                "point": self._sequence([(520, 0.08), (690, 0.11)], 0.55),
                "fault": self._sequence([(250, 0.09), (175, 0.14)], 0.52),
                "win": self._sequence([(440, 0.10), (554, 0.10), (659, 0.18)], 0.62),
                "connect": self._sequence([(480, 0.07), (720, 0.12)], 0.48),
                "disconnect": self._sequence([(320, 0.10), (220, 0.16)], 0.56),
                "fallback_music": self._music_track(),
            }
            self.enabled = True
            pygame.mixer.set_num_channels(max(8, pygame.mixer.get_num_channels()))
            pygame.mixer.set_reserved(1)
            self.music_channel = pygame.mixer.Channel(0)
            self._start_music()
        except pygame.error:
            self.enabled = False

    @staticmethod
    def _wave(phase: float, kind: str) -> float:
        if kind == "square":
            return 1.0 if math.sin(phase) >= 0.0 else -1.0
        if kind == "triangle":
            return (2.0 / math.pi) * math.asin(math.sin(phase))
        return math.sin(phase)

    def _tone(
        self,
        frequency: float,
        duration: float,
        volume: float,
        wave: str = "sine",
        attack: float = 0.01,
    ) -> pygame.mixer.Sound:
        count = max(1, int(AUDIO_SAMPLE_RATE * duration))
        release = min(0.04, duration * 0.45)
        samples = array.array("h")
        for i in range(count):
            t = i / AUDIO_SAMPLE_RATE
            env = 1.0
            if attack > 0 and t < attack:
                env = t / attack
            remaining = duration - t
            if release > 0 and remaining < release:
                env *= max(0.0, remaining / release)
            value = self._wave(2.0 * math.pi * frequency * t, wave)
            # Keep the generated sample unscaled so the mixer can apply the
            # full 0%-200% user range at playback time.  At 100%, applying
            # AUDIO_VOLUME below produces the same loudness as older builds.
            samples.append(int(32767 * volume * env * value))
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _sequence(self, notes: list[tuple[float, float]], volume: float) -> pygame.mixer.Sound:
        samples = array.array("h")
        for frequency, duration in notes:
            count = max(1, int(AUDIO_SAMPLE_RATE * duration))
            release = min(0.035, duration * 0.40)
            for i in range(count):
                t = i / AUDIO_SAMPLE_RATE
                env = min(1.0, t / 0.008)
                remaining = duration - t
                if remaining < release:
                    env *= max(0.0, remaining / release)
                value = math.sin(2.0 * math.pi * frequency * t)
                samples.append(int(32767 * volume * env * value))
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _music_track(self) -> pygame.mixer.Sound:
        """Create a short looping two-voice chiptune track."""
        beat = 0.18
        melody = [
            659.25, 0.0, 783.99, 0.0, 880.00, 783.99, 659.25, 523.25,
            587.33, 0.0, 659.25, 0.0, 783.99, 659.25, 587.33, 493.88,
            523.25, 0.0, 659.25, 0.0, 698.46, 659.25, 523.25, 440.00,
            493.88, 0.0, 587.33, 0.0, 659.25, 587.33, 493.88, 392.00,
        ]
        bass = [
            130.81, 130.81, 130.81, 130.81,
            146.83, 146.83, 146.83, 146.83,
            110.00, 110.00, 110.00, 110.00,
            123.47, 123.47, 123.47, 123.47,
            130.81, 130.81, 130.81, 130.81,
            146.83, 146.83, 146.83, 146.83,
            110.00, 110.00, 110.00, 110.00,
            98.00, 98.00, 123.47, 123.47,
        ]

        total_samples = int(AUDIO_SAMPLE_RATE * beat * len(melody))
        samples = array.array("h")

        for i in range(total_samples):
            t = i / AUDIO_SAMPLE_RATE
            step = min(len(melody) - 1, int(t / beat))
            local_t = t - step * beat

            # Short note envelope keeps the loop rhythmic rather than droning.
            note_env = 1.0
            if local_t < 0.008:
                note_env = local_t / 0.008
            release_start = beat * 0.72
            if local_t > release_start:
                note_env *= max(0.0, (beat - local_t) / (beat - release_start))

            melody_freq = melody[step]
            melody_sample = 0.0
            if melody_freq > 0.0:
                phase = 2.0 * math.pi * melody_freq * t
                melody_sample = 0.62 * self._wave(phase, "triangle")

            bass_freq = bass[step]
            bass_phase = 2.0 * math.pi * bass_freq * t
            bass_sample = 0.33 * math.sin(bass_phase)

            # A tiny pulse on each beat acts like simple percussion.
            pulse = 0.0
            if local_t < 0.035:
                pulse_env = 1.0 - (local_t / 0.035)
                pulse = 0.16 * pulse_env * math.sin(
                    2.0 * math.pi * (95.0 - 45.0 * local_t / 0.035) * t
                )

            mixed = (melody_sample * note_env) + bass_sample + pulse
            mixed = max(-1.0, min(1.0, mixed))
            samples.append(int(32767 * BUILT_IN_TRACK_GAIN * mixed))

        return pygame.mixer.Sound(buffer=samples.tobytes())

    @staticmethod
    def _music_directory() -> Path:
        return Path(__file__).resolve().parent / "music"

    def music_choices(self) -> list[str]:
        """Return the built-in track plus every supported file in music/."""
        folder = self._music_directory()
        folder.mkdir(parents=True, exist_ok=True)

        candidates = sorted(
            (
                path for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_MUSIC_SUFFIXES
            ),
            key=lambda path: path.name.lower(),
        )
        return [BUILT_IN_MUSIC, *(path.name for path in candidates)]

    def _find_custom_music(self) -> Optional[Path]:
        folder = self._music_directory()
        folder.mkdir(parents=True, exist_ok=True)

        if self.selected_music == BUILT_IN_MUSIC:
            return None

        if self.selected_music:
            selected_path = folder / self.selected_music
            if (
                selected_path.is_file()
                and selected_path.suffix.lower() in SUPPORTED_MUSIC_SUFFIXES
            ):
                return selected_path
            # A selected file was removed or renamed. Fall back cleanly.
            self.selected_music = BUILT_IN_MUSIC
            return None

        # Backward compatibility for players upgrading from older builds:
        # when no selection has ever been saved, use the old preferred-file
        # rules instead of unexpectedly changing their current music.
        preferred = [
            folder / "gameplay.ogg",
            folder / "gameplay.mp3",
            folder / "gameplay.wav",
        ]
        for path in preferred:
            if path.is_file():
                return path

        candidates = sorted(
            (
                path for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_MUSIC_SUFFIXES
            ),
            key=lambda path: path.name.lower(),
        )
        return candidates[0] if candidates else None

    def _stop_music(self) -> None:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        if self.music_channel is not None:
            self.music_channel.stop()

    def select_music(self, choice: str) -> str:
        """Select, immediately play, and persist one main-menu BGM choice."""
        choices = self.music_choices()
        if choice not in choices:
            return self.music_name

        self.selected_music = choice
        self._save_volume_settings()

        if not self.enabled or pygame.mixer.get_init() is None:
            return self.music_name

        self._stop_music()
        self._start_music()
        self._apply_music_muted_state()
        return self.music_name

    def _start_music(self) -> None:
        """Start a user-supplied music file, otherwise use the built-in fallback."""
        self.music_path = self._find_custom_music()
        self.using_streamed_music = False

        if self.music_path is not None:
            try:
                pygame.mixer.music.load(str(self.music_path))
                pygame.mixer.music.play(-1)
                self.using_streamed_music = True
                # Apply after play(). Some SDL_mixer backends can reset their
                # stream gain while starting or looping a decoded music file.
                self.maintain_output_levels(force=True)
                return
            except pygame.error:
                # Unsupported/corrupt files should not stop the game from starting.
                self.music_path = None
                self.selected_music = BUILT_IN_MUSIC
                self._save_volume_settings()

        if self.music_channel is not None:
            self.music_channel.play(self.sounds["fallback_music"], loops=-1)
            self.maintain_output_levels(force=True)

    @property
    def music_name(self) -> str:
        if self.music_path is not None:
            return self.music_path.name
        return BUILT_IN_MUSIC

    def _apply_music_muted_state(self) -> None:
        if not self.music_muted:
            return
        if self.using_streamed_music:
            pygame.mixer.music.pause()
        elif self.music_channel is not None:
            self.music_channel.pause()

    def reload_music(self) -> str:
        """Reload the music folder without restarting the game."""
        self._stop_music()

        self._start_music()
        self._apply_music_muted_state()
        self._save_volume_settings()

        return self.music_name

    def play(self, name: str, signature: Optional[tuple] = None) -> None:
        if not self.enabled or self.sfx_muted:
            return
        if signature is not None:
            if signature in self._seen_events:
                return
            self._seen_events.add(signature)
            self._seen_order.append(signature)
            if len(self._seen_order) > 800:
                old = self._seen_order.pop(0)
                self._seen_events.discard(old)
        sound = self.sounds.get(name)
        if sound is not None:

            # pygame caps Sound volume at 1.0.  The samples are left unscaled
            # when generated, which lets 200% become twice the 100% baseline
            # without asking pygame to accept an out-of-range value.
            sound.set_volume(self._sfx_output_volume())

            sound.play()


    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = round(max(0.0, min(MAX_USER_VOLUME, volume)), 2)
        self._save_volume_settings()
        self.maintain_output_levels(force=True)

    def set_music_volume(self, volume: float) -> None:
        self.music_volume = round(max(0.0, min(MAX_USER_VOLUME, volume)), 2)
        self._save_volume_settings()

        self.maintain_output_levels(force=True)

    def _music_output_volume(self) -> float:
        return min(1.0, MUSIC_VOLUME * self.music_volume)

    def _sfx_output_volume(self) -> float:
        return min(1.0, AUDIO_VOLUME * self.sfx_volume)

    def maintain_output_levels(self, force: bool = False) -> None:
        """Keep the selected levels from drifting while audio is playing.

        Pygame normally retains mixer levels, but some SDL_mixer/platform
        combinations can reset decoded-stream or channel gain on playback and
        loop boundaries. Reapplying four times a second is inexpensive and
        prevents that gradual softening without restarting the track.
        """
        if not self.enabled or pygame.mixer.get_init() is None:
            return

        now = time.monotonic()
        if not force and now - self._last_level_apply < 0.25:
            return
        self._last_level_apply = now

        music_level = self._music_output_volume()
        sfx_level = self._sfx_output_volume()
        try:
            if self.using_streamed_music:
                pygame.mixer.music.set_volume(music_level)
            elif self.music_channel is not None:
                self.music_channel.set_volume(music_level)

            for name, sound in self.sounds.items():
                if name != "fallback_music":
                    sound.set_volume(sfx_level)
        except pygame.error:
            # A transient device error should not interrupt gameplay. The next
            # scheduled pass will try to restore the levels again.
            pass

    def change_sfx_volume(self, direction: int) -> float:
        """Move SFX volume one 10% step and return the new multiplier."""
        self.set_sfx_volume(self.sfx_volume + VOLUME_STEP * direction)
        return self.sfx_volume

    def change_music_volume(self, direction: int) -> float:
        """Move music volume one 10% step and return the new multiplier."""
        self.set_music_volume(self.music_volume + VOLUME_STEP * direction)
        return self.music_volume

    def toggle_music(self) -> bool:
        self.music_muted = not self.music_muted
        if not self.enabled or pygame.mixer.get_init() is None:
            return self.music_muted

        if self.using_streamed_music:
            if self.music_muted:
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
                self.maintain_output_levels(force=True)
        elif self.music_channel is not None:
            if self.music_muted:
                self.music_channel.pause()
            else:
                self.music_channel.unpause()
                self.maintain_output_levels(force=True)
        return self.music_muted

    def toggle_sfx(self) -> bool:
        self.sfx_muted = not self.sfx_muted
        return self.sfx_muted

    def observe(self, before: WorldState, after: WorldState) -> None:
        frame = after.frame
        if after.winner and after.winner != before.winner:
            self.play("win", ("win", frame, after.winner, after.score1, after.score2))
            return

        if (after.score1, after.score2) != (before.score1, before.score2):
            reason = after.message.upper()
            effect = "fault" if any(word in reason for word in ("NET", "OUT", "WRONG SIDE")) else "point"
            self.play(effect, ("score", frame, after.score1, after.score2))
            return

        hit_happened = (
            (before.ball.attached and not after.ball.attached)
            or (after.ball.last_hitter != before.ball.last_hitter and after.ball.last_hitter != 0)
        )
        if hit_happened:
            effect = "serve" if before.ball.attached else "hit"
            self.play(effect, (effect, frame, after.ball.last_hitter))

        bounced = (
            not after.ball.attached
            and (
                after.ball.bounce_side != before.ball.bounce_side
                or after.ball.bounces_on_side > before.ball.bounces_on_side
            )
        )
        if bounced:
            self.play("bounce", ("bounce", frame, after.ball.bounce_side, after.ball.bounces_on_side))


    # added
    def _save_volume_settings(self) -> None:
        try:
            AUDIO_SAVE.parent.mkdir(parents=True, exist_ok=True)

            AUDIO_SAVE.write_text(
                json.dumps(
                    {
                        "sfx_volume": self.sfx_volume,
                        "music_volume": self.music_volume,
                        "selected_music": self.selected_music,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    # added
    def _load_volume_settings(self) -> None:
        try:
            data = json.loads(AUDIO_SAVE.read_text(encoding="utf-8"))

            self.sfx_volume = max(
                0.0,
                min(MAX_USER_VOLUME, float(data.get("sfx_volume", 1.0)))
            )

            self.music_volume = max(
                0.0,
                min(MAX_USER_VOLUME, float(data.get("music_volume", 1.0)))
            )

            selected_music = data.get("selected_music")
            self.selected_music = selected_music if isinstance(selected_music, str) else None

        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.sfx_volume = 1.0
            self.music_volume = 1.0
            self.selected_music = None

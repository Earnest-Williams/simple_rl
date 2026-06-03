"""Sound system for BasicRL.

This module provides a comprehensive sound effects and background music system
that integrates with the game's event-driven architecture. It supports:

- Situational background music based on game state
- Context-aware sound effects
- Distance-based audio falloff
- Environmental audio effects
- Volume and audio settings management

The sound system is designed to be non-intrusive and can be disabled entirely
through configuration.

This module is audio-only. It may use already-computed flow-cost fields to
attenuate playback volume, but it must not own or run pathfinding sound/scent
propagation. Gameplay systems should emit typed perception events elsewhere and
let ``GameState``/``pathfinding.perception_systems`` update simulation fields.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import structlog
from numpy.typing import NDArray

from game.world import line_of_sight
from pathfinding.perception_systems import BASE_FLOW_CENTER, NOISE_STRENGTH
from utils.game_rng import GameRNG

if TYPE_CHECKING:
    import yaml as yaml_module
else:
    yaml_module: Any | None = None

_yaml_spec = importlib.util.find_spec("yaml")
if _yaml_spec is not None:
    yaml_module = importlib.import_module("yaml")

if TYPE_CHECKING:
    from pydub import AudioSegment

    from game.world.game_map import GameMap

log = structlog.get_logger(__name__)

# NumPy scalar precision is dtype-dependent, so Any is required by numpy.typing.
FlowCostMap = NDArray[np.integer[Any]]

# SDL_mixer configuration
SDL_MIXER_FREQUENCY: Final[int] = 22050  # Hz
SDL_MIXER_CHANNELS: Final[int] = 2  # Stereo
SDL_MIXER_CHUNK_SIZE: Final[int] = 512  # Buffer size in samples

# Audio backend detection - SDL_mixer only
AUDIO_BACKEND: str | None = None
sdl2_module: Any | None = None
sdl_mixer: Any | None = None

if (
    importlib.util.find_spec("sdl2") is not None
    and importlib.util.find_spec("sdl2.sdlmixer") is not None
):
    sdl2_module = importlib.import_module("sdl2")
    sdl_mixer = importlib.import_module("sdl2.sdlmixer")
    AUDIO_BACKEND = "sdl_mixer"
    log.info("Using SDL_mixer audio backend")
else:
    log.warning("SDL_mixer not available - sound system will be disabled")


class SoundEffect:
    """Represents a single sound effect with its properties."""

    def __init__(
        self, config: dict[str, Any], base_path: Path, rng: GameRNG | None = None
    ) -> None:
        self.effect_type = config.get("type", "file")
        self.files = config.get("files", [])
        self.generator = config.get("generator")
        self.settings = config.get("settings", {})
        self.volume = config.get("volume", 1.0)
        self.random_pitch = config.get("random_pitch", 0.0)
        self.conditions = config.get("conditions", {})
        self.base_path = base_path
        self._loaded_sounds = {}
        self.rng = rng if rng is not None else GameRNG()

    def get_random_file(self) -> Path | None:
        """Get a random sound file from the available options."""
        if not self.files:
            return None
        chosen_file = self.files[self.rng.get_int(0, len(self.files) - 1)]
        return self.base_path / chosen_file

    def matches_conditions(self, context: dict[str, Any]) -> bool:
        """Check if this sound effect matches the given context."""
        for condition_key, condition_value in self.conditions.items():
            context_value = context.get(condition_key)

            if isinstance(condition_value, list):
                if context_value not in condition_value:
                    return False
            else:
                if context_value != condition_value:
                    return False
        return True


class BackgroundMusic:
    """Represents background music with situational awareness."""

    def __init__(self, config: dict[str, Any], base_path: Path) -> None:
        # ``generator`` holds parameters for :class:`MusicGenerator`
        self.generator_settings = config.get("generator", {})
        self.volume = config.get("volume", 1.0)
        self.loop = config.get("loop", True)
        self.fade_in_time = config.get("fade_in_time", 1.0)
        self.fade_out_time = config.get("fade_out_time", 1.0)
        self.priority = config.get("priority", 0)
        self.conditions = config.get("conditions", {})
        self.base_path = base_path
        self._current_track = None

    def generate(self, context: dict[str, Any]) -> Path | None:
        """Generate background music using configured parameters.

        ``context`` may override tempo, harmony or intensity if those keys are
        present.  The function returns a temporary WAV file or ``None`` on
        failure.
        """
        settings = dict(self.generator_settings)
        for key in ("tempo", "harmony", "intensity"):
            if key in context:
                settings[key] = context[key]
        try:
            from game.audio.music import MusicGenerator

            generator = MusicGenerator()
            return generator.generate(**settings)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning(f"Failed to generate music: {exc}")
            return None

    def matches_conditions(self, context: dict[str, Any]) -> bool:
        """Check if this background music matches the current game context."""
        for condition_key, condition_value in self.conditions.items():
            context_value = context.get(condition_key)

            if condition_key == "min_depth":
                player_depth = context.get("depth", 0)
                if player_depth < condition_value:
                    return False
            elif isinstance(condition_value, list):
                if context_value not in condition_value:
                    return False
            else:
                if context_value != condition_value:
                    return False
        return True


class SoundManager:
    """Main sound system manager."""

    @staticmethod
    def _extract_flow_cost_map(context: dict[str, Any]) -> FlowCostMap | None:
        """Return an integer pathfinding flow-cost map from an audio context.

        ``flow_cost_map`` is the preferred key. ``noise_flow_cost`` is accepted
        as a descriptive alias. A legacy ``noise_map`` key is accepted only when
        it is integer typed; float radius/debug maps are ignored because
        ``_calculate_volume()`` interprets values as costs relative to
        ``BASE_FLOW_CENTER``.
        """
        candidate = context.get("flow_cost_map")
        if candidate is None:
            candidate = context.get("noise_flow_cost")
        if candidate is None:
            candidate = context.get("noise_map")

        if candidate is None:
            return None
        if not isinstance(candidate, np.ndarray):
            log.warning("Ignoring non-array flow-cost map in sound context")
            return None
        if candidate.ndim != 2:
            log.warning("Ignoring flow-cost map with invalid dimensions (must be 2D)")
            return None
        if not np.issubdtype(candidate.dtype, np.integer):
            log.warning(
                "Ignoring non-integer sound attenuation map; pass flow_cost_map "
                "from pathfinding perception fields instead of a float debug map"
            )
            return None
        return candidate

    def __init__(
        self, config_path: Path | None = None, rng: GameRNG | None = None
    ) -> None:
        self.enabled = False
        self.sound_effects: dict[str, SoundEffect] = {}
        self.background_music: dict[str, BackgroundMusic] = {}
        self.event_mappings: dict[str, str] = {}
        self.situational_modifiers: dict[str, Any] = {}
        self.current_music = None
        self.current_music_name = None
        self.current_music_file: Path | None = None
        self.active_sounds: dict[int, Any] = {}
        self.listener_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.listener_orientation: tuple[float, float] = (0.0, 1.0)
        self.rng = rng if rng is not None else GameRNG()

        # Audio settings
        self.master_volume = 1.0
        self.sfx_volume = 1.0
        self.music_volume = 1.0
        self.max_concurrent_sounds = 8
        self.sound_fade_distance = 10

        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "sounds.yaml"

        try:
            self._load_config(config_path)
            if AUDIO_BACKEND and self.enabled:
                self._initialize_audio_backend()
        except Exception as e:
            log.warning(f"Failed to initialize sound system: {e}")
            self.enabled = False

    def _load_config(self, config_path: Path) -> None:
        """Load sound configuration from YAML file."""
        if not config_path.exists():
            log.warning(f"Sound config file not found: {config_path}")
            return

        if yaml_module is None:
            log.warning("PyYAML is not available; sound configuration not loaded")
            return

        with open(config_path, encoding="utf-8") as f:
            config = yaml_module.safe_load(f)

        # Load general audio settings
        audio_config = config.get("audio", {})
        self.enabled = audio_config.get("enabled", True) and AUDIO_BACKEND is not None
        self.master_volume = audio_config.get("master_volume", 1.0)
        self.sfx_volume = audio_config.get("sfx_volume", 1.0)
        self.music_volume = audio_config.get("music_volume", 1.0)
        self.max_concurrent_sounds = audio_config.get("max_concurrent_sounds", 8)
        self.sound_fade_distance = audio_config.get("sound_fade_distance", 10)

        # Load sound effects
        sfx_config = config.get("sound_effects", {})
        base_sound_path = config_path.parent / "sounds"

        for sfx_name, sfx_data in sfx_config.items():
            self.sound_effects[sfx_name] = SoundEffect(
                sfx_data, base_sound_path, self.rng
            )

        # Load background music
        music_config = config.get("background_music", {})
        base_music_path = config_path.parent / "music"

        for music_name, music_data in music_config.items():
            self.background_music[music_name] = BackgroundMusic(
                music_data, base_music_path
            )

        # Load event mappings
        self.event_mappings = config.get("event_mappings", {})

        # Load situational modifiers
        self.situational_modifiers = config.get("situational_modifiers", {})

        log.info(
            f"Loaded sound config: {len(self.sound_effects)} effects, {len(self.background_music)} music tracks"
        )

    def _initialize_audio_backend(self) -> None:
        """Initialize the audio backend."""
        if not self.enabled:
            return

        if AUDIO_BACKEND != "sdl_mixer" or sdl_mixer is None or sdl2_module is None:
            log.error("SDL_mixer backend not available at runtime")
            self.enabled = False
            return

        init_result = sdl2_module.SDL_Init(sdl2_module.SDL_INIT_AUDIO)
        if init_result != 0:
            error_message = sdl2_module.SDL_GetError()
            log.error(f"Failed to init SDL audio: {error_message}")
            self.enabled = False
            return

        init_flags = getattr(sdl_mixer, "MIX_INIT_OGG", 0)
        if init_flags:
            loaded_flags = sdl_mixer.Mix_Init(init_flags)
            if loaded_flags & init_flags != init_flags:
                log.warning("SDL_mixer OGG support not fully available")

        format_value = sdl2_module.AUDIO_S16SYS
        open_result = sdl_mixer.Mix_OpenAudio(
            SDL_MIXER_FREQUENCY,
            format_value,
            SDL_MIXER_CHANNELS,
            SDL_MIXER_CHUNK_SIZE,
        )
        if open_result != 0:
            error_message = sdl_mixer.Mix_GetError()
            log.error(f"Failed to open SDL_mixer audio: {error_message}")
            self.enabled = False
            return

        sdl_mixer.Mix_AllocateChannels(self.max_concurrent_sounds)
        log.info("SDL_mixer audio backend initialized")

    def play_sound_effect(
        self, effect_name: str, context: dict[str, Any] | None = None
    ) -> bool:
        """Play a sound effect with the given context."""
        if not self.enabled or effect_name not in self.sound_effects:
            return False

        effect = self.sound_effects[effect_name]

        # Check if sound matches context conditions
        if context and not effect.matches_conditions(context):
            return False

        # Get sound file or generate procedural audio
        cleanup_files: list[Path] = []
        if effect.effect_type == "procedural":
            try:
                from game.audio import synthesis

                temp_file = synthesis.generate_sound(
                    effect.generator or "", effect.settings
                )
                cleanup_files.append(temp_file)
                sound_file = temp_file
            except Exception as exc:
                log.warning(f"Failed to generate procedural sound {effect_name}: {exc}")
                return False
        else:
            sound_file = effect.get_random_file()
        if not sound_file:
            return False

        source_pos: tuple[float, float] | None = None
        listener_pos: tuple[float, float, float] = self.listener_position
        listener_orient: tuple[float, float] = self.listener_orientation
        game_map: GameMap | None = None
        flow_cost_map: FlowCostMap | None = None
        if context:
            source_pos = context.get("source_position") or context.get("position")
            lp = context.get("listener_position")
            if lp:
                listener_pos = (lp[0], lp[1], 0.0) if len(lp) == 2 else tuple(lp)
            lo = context.get("listener_orientation")
            if lo:
                listener_orient = (lo[0], lo[1])
            game_map = context.get("game_map")
            flow_cost_map = self._extract_flow_cost_map(context)
            if source_pos and "distance" not in context:
                sx, sy = source_pos
                lx, ly, lz = listener_pos
                dist = math.hypot(sx - lx, sy - ly)
                context = dict(context)
                context["distance"] = dist

        # Calculate volume with modifiers
        volume = self._calculate_volume(
            effect.volume,
            context,
            source_pos,
            listener_pos,
            listener_orient,
            game_map,
            flow_cost_map,
        )

        # Apply environment DSP effects
        if context:
            processed = self._apply_environment_effects(sound_file, context)
            if processed != sound_file:
                cleanup_files.append(processed)
                sound_file = processed

        self._prune_finished_sounds()

        # Limit concurrent sounds
        if len(self.active_sounds) >= self.max_concurrent_sounds:
            return False

        try:
            played = self._play_sound_file(
                sound_file,
                volume,
                effect.random_pitch,
                source_pos,
                listener_pos,
                listener_orient,
            )
            if not played and AUDIO_BACKEND is None:
                # Treat as success in environments without an audio backend
                played = True
            return played
        except Exception as e:
            log.warning(f"Failed to play sound effect {effect_name}: {e}")
            return False
        finally:
            for temp in cleanup_files:
                with contextlib.suppress(Exception):
                    temp.unlink()

    def update_background_music(self, context: dict[str, Any]) -> None:
        """Update background music based on current game context."""
        if not self.enabled:
            return

        # Find the best matching music track
        best_music = None
        best_priority = -1
        best_name = None

        for music_name, music in self.background_music.items():
            if music.matches_conditions(context) and music.priority > best_priority:
                best_music = music
                best_priority = music.priority
                best_name = music_name

        # Switch music if needed
        if best_name != self.current_music_name:
            self._switch_background_music(best_music, best_name, context)

    def _switch_background_music(
        self,
        new_music: BackgroundMusic | None,
        music_name: str | None,
        context: dict[str, Any],
    ) -> None:
        """Switch to new background music with proper fading."""
        if not self.enabled:
            return

        # Stop current music
        if self.current_music or self.current_music_file:
            self._stop_background_music()

        # Start new music using the generator
        if new_music:
            music_file = new_music.generate(context)
            if music_file:
                volume = self._calculate_music_volume(new_music.volume, context)
                try:
                    self._play_background_music_file(music_file, volume, new_music.loop)
                    self.current_music_name = music_name
                    self.current_music_file = music_file
                    log.debug(f"Switched to background music: {music_name}")
                except Exception as e:
                    log.warning(f"Failed to play background music {music_name}: {e}")
                    self.current_music_file = None

    def _calculate_volume(
        self,
        base_volume: float,
        context: dict[str, Any] | None = None,
        source_pos: tuple[float, float] | None = None,
        listener_pos: tuple[float, float, float] | None = None,
        listener_orientation: tuple[float, float] | None = None,
        game_map: GameMap | None = None,
        flow_cost_map: FlowCostMap | None = None,
    ) -> float:
        """Calculate final volume with all modifiers applied."""
        final_volume = base_volume * self.sfx_volume * self.master_volume

        if context is None:
            context = {}

        # Apply distance-based falloff if not handled by backend
        distance = context.get("distance", 0)
        if distance > 0 and self.sound_fade_distance > 0:
            distance_modifier = max(0.0, 1.0 - (distance / self.sound_fade_distance))
            final_volume *= distance_modifier

        # Apply environmental modifiers
        environment = context.get("environment")
        if environment and "environment_effects" in self.situational_modifiers:
            env_effects = self.situational_modifiers["environment_effects"].get(
                environment, {}
            )
            volume_modifier = env_effects.get("volume_modifier", 1.0)
            final_volume *= volume_modifier

        # Apply time-of-day modifiers
        time_of_day = context.get("time_of_day")
        if time_of_day and "time_of_day" in self.situational_modifiers:
            tod_effects = self.situational_modifiers["time_of_day"].get(time_of_day, {})
            final_volume *= tod_effects.get("volume_modifier", 1.0)

        occlusion_cfg = self.situational_modifiers.get("occlusion", {})

        # Apply attenuation based on a precomputed pathfinding flow-cost map.
        if flow_cost_map is not None and listener_pos is not None:
            nx = int(listener_pos[0])
            ny = int(listener_pos[1])
            if 0 <= ny < flow_cost_map.shape[0] and 0 <= nx < flow_cost_map.shape[1]:
                cost = int(flow_cost_map[ny, nx])
                infinity = np.iinfo(flow_cost_map.dtype).max // 2
                if cost < infinity:
                    noise_dist = cost - BASE_FLOW_CENTER
                    if NOISE_STRENGTH > 0:
                        noise_modifier = max(0.0, 1.0 - (noise_dist / NOISE_STRENGTH))
                        final_volume *= noise_modifier
                else:
                    final_volume = 0.0

        # Apply directional attenuation for sounds behind the listener
        if source_pos and listener_pos and listener_orientation:
            dx = source_pos[0] - listener_pos[0]
            dy = source_pos[1] - listener_pos[1]
            dist = math.hypot(dx, dy)
            if dist > 0:
                ox, oy = listener_orientation
                dot = (dx * ox + dy * oy) / dist
                if dot < 0:
                    rear = occlusion_cfg.get("rear_attenuation", 0.5)
                    final_volume *= rear

        # Apply occlusion based on map data
        if (
            source_pos
            and listener_pos
            and game_map
            and occlusion_cfg
            and not line_of_sight(
                int(listener_pos[0]),
                int(listener_pos[1]),
                int(source_pos[0]),
                int(source_pos[1]),
                game_map.transparent,
            )
        ):
            wall_abs = occlusion_cfg.get("wall_absorption", 0.5)
            final_volume *= 1.0 - wall_abs

        return max(0.0, min(1.0, final_volume))

    def _apply_environment_effects(self, fname: Path, context: dict[str, Any]) -> Path:
        """Apply environmental DSP effects and return processed file path."""
        env_name = context.get("environment")
        if not env_name or "environment_effects" not in self.situational_modifiers:
            return fname
        env_cfg = self.situational_modifiers["environment_effects"].get(env_name, {})
        tod_cfg: dict[str, Any] = {}
        time_of_day = context.get("time_of_day")
        if time_of_day and "time_of_day" in self.situational_modifiers:
            tod_cfg = self.situational_modifiers["time_of_day"].get(time_of_day, {})

        reverb_amt = env_cfg.get("reverb")
        lp_amt = env_cfg.get("low_pass_filter")
        eq_cfg = env_cfg.get("eq")
        if reverb_amt is None and lp_amt is None and not eq_cfg:
            return fname

        from tempfile import NamedTemporaryFile

        from pydub import AudioSegment, effects

        try:
            segment = AudioSegment.from_file(fname)
        except Exception:
            # Fallback for environments without ffmpeg when using wav files
            segment = AudioSegment.from_wav(fname)
        if reverb_amt:
            reverb_amt *= tod_cfg.get("reverb_modifier", 1.0)
            segment = self._add_reverb(segment, reverb_amt)
        if lp_amt:
            lp_amt *= tod_cfg.get("low_pass_modifier", 1.0)
            cutoff = int(2000 + (8000 * (1.0 - max(0.0, min(1.0, lp_amt)))))
            segment = effects.low_pass_filter(segment, cutoff)
        if eq_cfg:
            segment = self._apply_eq(segment, eq_cfg)

        with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            segment.export(tmp.name, format="wav")
            return Path(tmp.name)

    def _add_reverb(self, segment: AudioSegment, amount: float) -> AudioSegment:
        """Simple reverb using delayed overlays."""
        delay = int(50 + 150 * amount)
        decay = 0.6 * amount
        echo = segment - 20
        for i in range(1, 4):
            segment = segment.overlay(
                echo, position=delay * i, gain_during_overlay=-decay * i * 10
            )
        return segment

    def _apply_eq(
        self, segment: AudioSegment, eq_cfg: dict[str, float]
    ) -> AudioSegment:
        """Very simple two-band EQ for bass and treble adjustments."""
        bass_gain = eq_cfg.get("bass")
        treble_gain = eq_cfg.get("treble")
        if bass_gain is not None:
            bass = segment.low_pass_filter(200).apply_gain(bass_gain)
            high = segment.high_pass_filter(200)
            segment = bass.overlay(high)
        if treble_gain is not None:
            treble = segment.high_pass_filter(4000).apply_gain(treble_gain)
            mid = segment.low_pass_filter(4000)
            segment = mid.overlay(treble)
        return segment

    def _calculate_music_volume(
        self, base_volume: float, context: dict[str, Any]
    ) -> float:
        """Calculate background music volume with modifiers."""
        return max(0.0, min(1.0, base_volume * self.music_volume * self.master_volume))

    def _prune_finished_sounds(self) -> None:
        """Remove finished sound handles from active list."""
        if not self.active_sounds:
            return
        if AUDIO_BACKEND != "sdl_mixer" or sdl_mixer is None:
            return
        finished_channels: list[int] = []
        for channel in self.active_sounds:
            if sdl_mixer.Mix_Playing(channel) == 0:
                finished_channels.append(channel)
        for channel in finished_channels:
            chunk = self.active_sounds.pop(channel, None)
            if chunk is None:
                continue
            with contextlib.suppress(Exception):
                sdl_mixer.Mix_FreeChunk(chunk)

    def _calculate_pan(
        self,
        source_pos: tuple[float, float],
        listener_pos: tuple[float, float, float],
        listener_orientation: tuple[float, float],
    ) -> float:
        """Return stereo pan value (-1.0 left to 1.0 right)."""
        dx = source_pos[0] - listener_pos[0]
        dy = source_pos[1] - listener_pos[1]
        angle_to_source = math.atan2(dy, dx)
        listener_angle = math.atan2(listener_orientation[1], listener_orientation[0])
        angle = angle_to_source - listener_angle
        pan = math.sin(angle)
        return max(-1.0, min(1.0, pan))

    def _play_sound_file(
        self,
        filename: Path,
        volume: float,
        pitch_variance: float = 0.0,
        source_pos: tuple[float, float] | None = None,
        listener_pos: tuple[float, float, float] | None = None,
        listener_orientation: tuple[float, float] | None = None,
    ) -> bool:
        """Play a sound file using the current audio backend."""
        fname = str(filename)
        if AUDIO_BACKEND != "sdl_mixer" or sdl_mixer is None:
            log.debug(f"No audio backend to play sound: {fname}")
            return False

        if pitch_variance:
            log.debug("SDL_mixer backend does not support pitch variance.")

        try:
            chunk = sdl_mixer.Mix_LoadWAV(fname.encode("utf-8"))
            if not chunk:
                log.warning(f"SDL_mixer failed to load sound {fname}")
                return False
            channel = sdl_mixer.Mix_PlayChannel(-1, chunk, 0)
            if channel == -1:
                sdl_mixer.Mix_FreeChunk(chunk)
                log.warning(f"SDL_mixer failed to play sound {fname}")
                return False
            volume_value = int(max(0.0, min(1.0, volume)) * 128)
            sdl_mixer.Mix_Volume(channel, volume_value)
            if source_pos and listener_pos and listener_orientation:
                pan = self._calculate_pan(
                    source_pos, listener_pos, listener_orientation
                )
                left = int(((1.0 - pan) / 2.0) * 255)
                right = int(((1.0 + pan) / 2.0) * 255)
                sdl_mixer.Mix_SetPanning(channel, left, right)
            else:
                sdl_mixer.Mix_SetPanning(channel, 255, 255)
            self.active_sounds[channel] = chunk
            return True
        except Exception as exc:
            log.warning(f"SDL_mixer failed to play sound {fname}: {exc}")
            return False

    def _play_background_music_file(
        self, filename: Path, volume: float, loop: bool = True
    ) -> None:
        """Play background music using the current audio backend."""
        fname = str(filename)
        if AUDIO_BACKEND != "sdl_mixer" or sdl_mixer is None:
            log.debug(f"No audio backend to play music: {fname}")
            return
        try:
            music = sdl_mixer.Mix_LoadMUS(fname.encode("utf-8"))
            if not music:
                log.warning(f"SDL_mixer failed to load music {fname}")
                return
            volume_value = int(max(0.0, min(1.0, volume)) * 128)
            sdl_mixer.Mix_VolumeMusic(volume_value)
            loops = -1 if loop else 0
            result = sdl_mixer.Mix_PlayMusic(music, loops)
            if result != 0:
                sdl_mixer.Mix_FreeMusic(music)
                log.warning(f"SDL_mixer failed to play music {fname}")
                return
            self.current_music = music
        except Exception as exc:
            log.warning(f"SDL_mixer failed to play music {fname}: {exc}")

    def _stop_background_music(self) -> None:
        """Stop the current background music."""
        if self.current_music:
            log.debug(f"Stopping background music: {self.current_music_name}")
            if AUDIO_BACKEND == "sdl_mixer" and sdl_mixer is not None:
                with contextlib.suppress(Exception):
                    sdl_mixer.Mix_HaltMusic()
                with contextlib.suppress(Exception):
                    sdl_mixer.Mix_FreeMusic(self.current_music)

        if self.current_music_file:
            with contextlib.suppress(Exception):
                self.current_music_file.unlink()
            self.current_music_file = None

        self.current_music = None
        self.current_music_name = None

    def handle_game_event(
        self, event_name: str, context: dict[str, Any] | None = None
    ) -> None:
        """Handle a game event that might trigger sound effects."""
        if not self.enabled:
            return

        # Look up sound effect mapping
        sfx_name = self.event_mappings.get(event_name)
        if sfx_name:
            self.play_sound_effect(sfx_name, context)

    def set_master_volume(self, volume: float) -> None:
        """Set the master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))

    def set_sfx_volume(self, volume: float) -> None:
        """Set the sound effects volume (0.0 to 1.0)."""
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_music_volume(self, volume: float) -> None:
        """Set the background music volume (0.0 to 1.0)."""
        self.music_volume = max(0.0, min(1.0, volume))

    def set_listener_position(self, x: float, y: float, z: float = 0.0) -> None:
        """Update the 3D listener position."""
        self.listener_position = (x, y, z)

    def set_listener_orientation(self, x: float, y: float) -> None:
        """Update the 2D listener orientation vector."""
        length = math.hypot(x, y)
        if length == 0:
            return
        self.listener_orientation = (x / length, y / length)

    def enable_audio(self, enabled: bool) -> None:
        """Enable or disable the entire audio system."""
        if enabled and not AUDIO_BACKEND:
            log.warning("Cannot enable audio - no backend available")
            return

        self.enabled = enabled
        if not enabled and self.current_music:
            self._stop_background_music()

    def cleanup(self) -> None:
        """Clean up audio resources."""
        if self.enabled:
            self._stop_background_music()
            for channel, chunk in list(self.active_sounds.items()):
                try:
                    if AUDIO_BACKEND == "sdl_mixer" and sdl_mixer is not None:
                        sdl_mixer.Mix_HaltChannel(channel)
                        sdl_mixer.Mix_FreeChunk(chunk)
                except Exception:
                    pass
            self.active_sounds.clear()


# Global sound manager instance
_sound_manager: SoundManager | None = None


def get_sound_manager() -> SoundManager:
    """Get the global sound manager instance."""
    global _sound_manager
    if _sound_manager is None:
        _sound_manager = SoundManager()
    return _sound_manager


def init_sound_system(config_path: Path | None = None) -> SoundManager:
    """Initialize the global sound system."""
    global _sound_manager
    _sound_manager = SoundManager(config_path)
    return _sound_manager


def play_sound(effect_name: str, context: dict[str, Any] | None = None) -> bool:
    """Convenience function to play a sound effect."""
    return get_sound_manager().play_sound_effect(effect_name, context)


def handle_event(event_name: str, context: dict[str, Any] | None = None) -> None:
    """Convenience function to handle a game event."""
    get_sound_manager().handle_game_event(event_name, context)


def update_music_context(context: dict[str, Any]) -> None:
    """Convenience function to update background music context."""
    get_sound_manager().update_background_music(context)

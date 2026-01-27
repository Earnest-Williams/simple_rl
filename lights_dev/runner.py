from __future__ import annotations

import logging
import time
from typing import Callable

from lights_dev import constants
from lights_dev.fov import FOVSystem
from lights_dev.game_state import GameState
from lights_dev.lighting import LightingSystem
from lights_dev.memory import precompile as precompile_memory
from lights_dev.renderer import Renderer
from utils.game_rng import GameRNG


class GameRunner:
    """
    Lightweight runner to be embedded in a visual front-end.

    Usage:
        runner = GameRunner(80, 30, seed=12345)
        runner.initialize()
        runner.precompile()
        runner.step(dt)
        frame = runner.render()

    Notes:
    - Logging and event loop belong to the caller (no root-level logging config).
    - LOS uses np.bool_ and illumination uses np.float32 arrays shaped (H, W, 3).
    """

    def __init__(
        self,
        width: int,
        height: int,
        seed: int | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        self.seed: int = seed if seed is not None else int(time.time() * 1000)
        self.rng: GameRNG = GameRNG(seed=self.seed)
        self.game_state: GameState = GameState(width, height, self.rng)
        self.renderer: Renderer = renderer if renderer is not None else Renderer(
            constants.DEBUG_RENDER_MODE
        )
        self._last_frame_time: float = time.time()

    def initialize(self) -> None:
        """Create the map and place entities."""
        self.game_state.initialize_map_and_entities()

    def precompile(self) -> None:
        """
        Warm up Numba kernels. Safe to call once after initialize().
        Leaves logging to the caller and prints nothing.
        """
        d = self.game_state.dungeon
        if d is None or self.game_state.player is None:
            logging.info(
                "GameRunner.precompile: dungeon or player missing; skipping precompile."
            )
            return
        FOVSystem.precompile(d, self.game_state.player.position)
        LightingSystem.precompile(d, self.game_state.player.position)
        precompile_memory(d.height, d.width)

    def step(self, dt: float) -> None:
        """
        Advance the model by dt seconds. Updates state and visibility.
        """
        self.game_state.update(dt)
        self.game_state.update_visibility()

    def render(self) -> str:
        """Return the textual rendering from the configured renderer."""
        return self.renderer.render(self.game_state)

    def run_loop(self, frame_callback: Callable[[str], None] | None = None) -> None:
        """
        Convenience run loop for quick testing.
        Calls frame_callback with the rendered string each frame.
        """
        try:
            while True:
                now = time.time()
                dt = now - self._last_frame_time
                self._last_frame_time = now
                self.step(min(dt, 0.1))
                rendered = self.render()
                if frame_callback is not None:
                    frame_callback(rendered)
                else:
                    print("\033[H\033[J", end="")
                    print(rendered)
                time.sleep(1.0 / 60.0)
        except KeyboardInterrupt:
            return

    def set_renderer_mode(self, mode: str) -> None:
        """Switch renderer mode (e.g., 'normal', 'level', 'intensity')."""
        self.renderer.render_mode = mode

    def get_seed(self) -> int:
        return self.seed

from __future__ import annotations

import numpy as np

from game.systems.sound import SoundManager
from pathfinding.perception_systems import BASE_FLOW_CENTER


def test_sound_volume_ignores_float_debug_noise_map() -> None:
    manager = SoundManager(config_path=None)
    manager.sfx_volume = 1.0
    manager.master_volume = 1.0
    manager.sound_fade_distance = 0

    debug_noise_map = np.zeros((5, 5), dtype=np.float32)
    volume = manager._calculate_volume(
        1.0,
        context={},
        listener_pos=(2.0, 2.0, 0.0),
        flow_cost_map=SoundManager._extract_flow_cost_map(
            {"noise_map": debug_noise_map}
        ),
    )

    assert volume == 1.0


def test_sound_volume_accepts_integer_flow_cost_map() -> None:
    manager = SoundManager(config_path=None)
    manager.sfx_volume = 1.0
    manager.master_volume = 1.0
    manager.sound_fade_distance = 0

    flow_cost_map = np.full((5, 5), BASE_FLOW_CENTER, dtype=np.int32)
    volume = manager._calculate_volume(
        1.0,
        context={},
        listener_pos=(2.0, 2.0, 0.0),
        flow_cost_map=SoundManager._extract_flow_cost_map(
            {"flow_cost_map": flow_cost_map}
        ),
    )

    assert volume == 1.0

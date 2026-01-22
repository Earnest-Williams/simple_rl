from __future__ import annotations

import importlib.util
import types
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Tuple, cast

import pytest

if TYPE_CHECKING:
    import numpy as np


class ApplyLightingFn(Protocol):
    def __call__(
        self, base_rgb: Tuple[int, int, int], rgb_sum: np.ndarray, brightness: float
    ) -> Tuple[int, int, int]:
        ...


class ConstantsModule(Protocol):
    AMBIENT_COLOR_RGB: Tuple[int, int, int]


def _load_lights_dev_module() -> types.ModuleType:
    pytest.importorskip("numba")
    test_path = Path(__file__)
    if not test_path.exists():
        raise FileNotFoundError("test_lights_dev_color.py not found on disk.")
    repo_root = test_path.parent.parent
    if not repo_root.exists():
        raise FileNotFoundError("Repository root not found for lights_dev import.")
    module_path = repo_root / "lights_dev" / "main_game.py"
    if not module_path.exists():
        raise FileNotFoundError("lights_dev/main_game.py not found on disk.")
    spec = importlib.util.spec_from_file_location(
        "lights_dev_main_game", module_path
    )
    if spec is None or spec.loader is None:
        raise ImportError("Failed to build module spec for lights_dev.main_game.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get_apply_lighting_fn(module: types.ModuleType) -> ApplyLightingFn:
    candidate = getattr(module, "_apply_lighting_to_base", None)
    if candidate is None or not callable(candidate):
        raise AttributeError("lights_dev.main_game._apply_lighting_to_base not found.")
    return cast(ApplyLightingFn, candidate)


def _get_constants(module: types.ModuleType) -> ConstantsModule:
    candidate = getattr(module, "constants", None)
    if candidate is None:
        raise AttributeError("lights_dev.main_game.constants not found.")
    return cast(ConstantsModule, candidate)


def _expected_interpolate(
    factor: float,
    start_rgb: Tuple[int, int, int],
    end_rgb: Tuple[int, int, int],
) -> Tuple[int, int, int]:
    clamped = max(0.0, min(1.0, factor))
    r_val = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * clamped)
    g_val = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * clamped)
    b_val = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * clamped)
    return (
        max(0, min(255, r_val)),
        max(0, min(255, g_val)),
        max(0, min(255, b_val)),
    )


def test_apply_lighting_base_rgb_full_brightness() -> None:
    module = _load_lights_dev_module()
    apply_fn = _get_apply_lighting_fn(module)
    np = pytest.importorskip("numpy")
    base_rgb = (120, 180, 200)
    rgb_sum = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    result = apply_fn(base_rgb, rgb_sum, 1.0)
    assert result == base_rgb


def test_apply_lighting_clamps_brightness_above_one() -> None:
    module = _load_lights_dev_module()
    apply_fn = _get_apply_lighting_fn(module)
    np = pytest.importorskip("numpy")
    base_rgb = (80, 60, 40)
    rgb_sum = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    result = apply_fn(base_rgb, rgb_sum, 2.0)
    assert result == base_rgb


def test_apply_lighting_zero_brightness_returns_ambient() -> None:
    module = _load_lights_dev_module()
    apply_fn = _get_apply_lighting_fn(module)
    constants = _get_constants(module)
    np = pytest.importorskip("numpy")
    base_rgb = (200, 100, 50)
    rgb_sum = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    result = apply_fn(base_rgb, rgb_sum, 0.0)
    assert result == constants.AMBIENT_COLOR_RGB


def test_apply_lighting_interpolates_with_tinted_base() -> None:
    module = _load_lights_dev_module()
    apply_fn = _get_apply_lighting_fn(module)
    constants = _get_constants(module)
    np = pytest.importorskip("numpy")
    base_rgb = (100, 100, 100)
    rgb_sum = np.array([255.0, 0.0, 0.0], dtype=np.float32)
    expected = _expected_interpolate(0.5, constants.AMBIENT_COLOR_RGB, (100, 0, 0))
    result = apply_fn(base_rgb, rgb_sum, 0.5)
    assert result == expected

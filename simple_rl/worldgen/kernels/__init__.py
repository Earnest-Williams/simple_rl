from __future__ import annotations

from typing import List

from simple_rl.worldgen.kernels.advection import advect_moisture_step
from simple_rl.worldgen.kernels.erosion import (
    hydraulic_erosion_step,
    thermal_erosion_step,
)
from simple_rl.worldgen.kernels.geometry import (
    compute_cell_area,
    cross_3d,
    dot_3d,
    normalize_3d,
    spherical_triangle_area,
)
from simple_rl.worldgen.kernels.heap import (
    heap_decrease_key,
    heap_init,
    heap_pop_min,
    heap_push,
)
from simple_rl.worldgen.kernels.noise import (
    eval_noise_sphere,
    hash_gradient,
    noise_3d_multi_octave,
    noise_3d_single,
    octave_seed,
    smoothstep,
    splitmix64,
)
from simple_rl.worldgen.kernels.smoothing import smooth_f32_nbr4, smooth_i32_nbr4
from simple_rl.worldgen.kernels.union_find import (
    uf_build_components,
    uf_find,
    uf_init,
    uf_union,
)

__all__: List[str] = [
    "advect_moisture_step",
    "hydraulic_erosion_step",
    "thermal_erosion_step",
    "compute_cell_area",
    "cross_3d",
    "dot_3d",
    "normalize_3d",
    "spherical_triangle_area",
    "heap_decrease_key",
    "heap_init",
    "heap_pop_min",
    "heap_push",
    "eval_noise_sphere",
    "hash_gradient",
    "noise_3d_multi_octave",
    "noise_3d_single",
    "octave_seed",
    "smoothstep",
    "splitmix64",
    "uf_build_components",
    "uf_find",
    "uf_init",
    "uf_union",
    "smooth_f32_nbr4",
    "smooth_i32_nbr4",
]

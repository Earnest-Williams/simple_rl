from __future__ import annotations

from common.constants import Material
from worldgen.overland.schema import (
    Biome,
    HydroRole,
    OverlandBundle,
    SurfaceTransitionRequest,
    TransitionType,
)


def generate_transition_requests(bundle: OverlandBundle) -> list[SurfaceTransitionRequest]:
    seed = int(bundle.metadata["seed"])
    requests: list[SurfaceTransitionRequest] = []
    for row in bundle.tiles_df.iter_rows(named=True):
        material = int(row["material"])
        hydro_role = HydroRole(int(row["hydro_role"]))
        transition_type = _transition_for(material, hydro_role)
        if transition_type is None:
            continue
        requests.append(
            SurfaceTransitionRequest(
                source_x=int(row["x"]),
                source_y=int(row["y"]),
                transition_type=transition_type,
                target_kind=_target_for(transition_type),
                hydro_role=hydro_role,
                biome=Biome(int(row["biome"])),
                material=material,
                seed=seed + int(row["x"]) * 1_003 + int(row["y"]) * 9_176,
                tags=(_target_for(transition_type),),
            )
        )
    requests.extend(_feature_transition_requests(bundle, seed=seed))
    return requests


def _feature_transition_requests(
    bundle: OverlandBundle,
    *,
    seed: int,
) -> list[SurfaceTransitionRequest]:
    requests: list[SurfaceTransitionRequest] = []
    if bundle.features_df.is_empty():
        return requests
    tile_lookup = {
        (int(row["x"]), int(row["y"])): row for row in bundle.tiles_df.iter_rows(named=True)
    }
    for row in bundle.features_df.iter_rows(named=True):
        tags = str(row["tags"])
        if not tags.startswith("settlement;"):
            continue
        x = int(row["x"])
        y = int(row["y"])
        tile = tile_lookup.get((x, y))
        if tile is None:
            continue
        requests.append(
            SurfaceTransitionRequest(
                source_x=x,
                source_y=y,
                transition_type=TransitionType.SETTLEMENT_ENTRANCE,
                target_kind="settlement",
                hydro_role=HydroRole(int(tile["hydro_role"])),
                biome=Biome(int(tile["biome"])),
                material=int(tile["material"]),
                seed=seed + x * 1_003 + y * 9_176 + int(row["target_id"]),
                tags=tuple(part for part in tags.split(";") if part),
            )
        )
    return requests


def _transition_for(
    material: int,
    hydro_role: HydroRole,
) -> TransitionType | None:
    if material == int(Material.PONOR) or hydro_role == HydroRole.PONOR:
        return TransitionType.PONOR_DESCENT
    if hydro_role == HydroRole.KARST_WINDOW:
        return TransitionType.KARST_WINDOW
    if hydro_role == HydroRole.SPRING:
        return TransitionType.SPRING_SOURCE
    if material == int(Material.CAVE_MOUTH):
        return TransitionType.CAVE_ENTRANCE
    if material == int(Material.LAVA_TUBE_SKYLIGHT):
        return TransitionType.LAVA_TUBE_SKYLIGHT
    if material == int(Material.COLLAPSED_LAVA_TUBE):
        return TransitionType.COLLAPSED_LAVA_TUBE
    if material == int(Material.DOCK):
        return TransitionType.DOCK_ROUTE
    if material in {int(Material.TRAIL), int(Material.TRACK)}:
        return TransitionType.TRAIL_EXIT
    return None


def _target_for(transition_type: TransitionType) -> str:
    if transition_type in {
        TransitionType.CAVE_ENTRANCE,
        TransitionType.PONOR_DESCENT,
        TransitionType.KARST_WINDOW,
        TransitionType.SPRING_SOURCE,
    }:
        return "karst_subsurface"
    if transition_type in {
        TransitionType.LAVA_TUBE_SKYLIGHT,
        TransitionType.COLLAPSED_LAVA_TUBE,
    }:
        return "lava_tube"
    if transition_type == TransitionType.DOCK_ROUTE:
        return "water_route"
    if transition_type == TransitionType.SETTLEMENT_ENTRANCE:
        return "settlement"
    return "overland_route"

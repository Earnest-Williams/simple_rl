from __future__ import annotations

import polars as pl

from common.constants import Material
from worldgen.overland.schema import (
    Affordance,
    Biome,
    EvidenceTag,
    ElevationBand,
    FeatureType,
    HydroRole,
    OverlandBundle,
    Substrate,
    SurfaceTransitionRequest,
    TransitionType,
)


def generate_transition_requests(
    bundle: OverlandBundle,
) -> list[SurfaceTransitionRequest]:
    seed = int(bundle.metadata["seed"])
    requests: list[SurfaceTransitionRequest] = []
    context = _transition_context(bundle)
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
                evidence_tags=_transition_evidence_tags(
                    row,
                    transition_type=transition_type,
                    context=context,
                ),
                **_handoff_payload(
                    row,
                    transition_type=transition_type,
                    context=context,
                ),
            )
        )
    requests.extend(_feature_transition_requests(bundle, seed=seed, context=context))
    return requests


def transition_requests_to_df(
    requests: list[SurfaceTransitionRequest],
) -> pl.DataFrame:
    schema = {
        "source_x": pl.Int64,
        "source_y": pl.Int64,
        "transition_type": pl.Int64,
        "target_kind": pl.Utf8,
        "hydro_role": pl.Int64,
        "biome": pl.Int64,
        "material": pl.Int64,
        "seed": pl.Int64,
        "tags": pl.Utf8,
        "cave_type": pl.Utf8,
        "seasonal_state": pl.Utf8,
        "flow_group": pl.Int64,
        "connected_to_underground": pl.Boolean,
        "substrate": pl.Int64,
        "elevation_band": pl.Int64,
        "nearby_affordances": pl.Utf8,
        "handoff_tags": pl.Utf8,
        "evidence_tags": pl.List(pl.Int64),
    }
    if not requests:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(
        [
            {
                "source_x": request.source_x,
                "source_y": request.source_y,
                "transition_type": int(request.transition_type),
                "target_kind": request.target_kind,
                "hydro_role": int(request.hydro_role),
                "biome": int(request.biome),
                "material": request.material,
                "seed": request.seed,
                "tags": ";".join(request.tags),
                "cave_type": request.cave_type,
                "seasonal_state": request.seasonal_state,
                "flow_group": request.flow_group,
                "connected_to_underground": request.connected_to_underground,
                "substrate": request.substrate,
                "elevation_band": request.elevation_band,
                "nearby_affordances": ";".join(request.nearby_affordances),
                "handoff_tags": ";".join(request.handoff_tags),
                "evidence_tags": list(request.evidence_tags),
            }
            for request in requests
        ],
        schema=schema,
    )


def _feature_transition_requests(
    bundle: OverlandBundle,
    *,
    seed: int,
    context: dict[str, object],
) -> list[SurfaceTransitionRequest]:
    requests: list[SurfaceTransitionRequest] = []
    if bundle.features_df.is_empty():
        return requests
    tile_lookup = {
        (int(row["x"]), int(row["y"])): row
        for row in bundle.tiles_df.iter_rows(named=True)
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
                evidence_tags=_transition_evidence_tags(
                    tile,
                    transition_type=TransitionType.SETTLEMENT_ENTRANCE,
                    context=context,
                ),
                **_handoff_payload(
                    tile,
                    transition_type=TransitionType.SETTLEMENT_ENTRANCE,
                    context=context,
                ),
            )
        )
    return requests


def _transition_context(bundle: OverlandBundle) -> dict[str, object]:
    hydrology = {
        (int(row["x"]), int(row["y"])): row
        for row in bundle.hydrology_df.iter_rows(named=True)
    }
    affordances: dict[tuple[int, int], set[str]] = {}
    for row in bundle.affordances_df.iter_rows(named=True):
        key = (int(row["x"]), int(row["y"]))
        affordance = Affordance(int(row["affordance"])).name.lower()
        affordances.setdefault(key, set()).add(affordance)
    feature_tags: dict[tuple[int, int], set[str]] = {}
    feature_evidence_tags: dict[tuple[int, int], set[int]] = {}
    feature_types: dict[tuple[int, int], set[FeatureType]] = {}
    for row in bundle.features_df.iter_rows(named=True):
        key = (int(row["x"]), int(row["y"]))
        feature_tags.setdefault(key, set()).update(
            part for part in str(row["tags"]).split(";") if part
        )
        if "evidence_tags" in row and row["evidence_tags"] is not None:
            feature_evidence_tags.setdefault(key, set()).update(
                int(value) for value in row["evidence_tags"]
            )
        try:
            feature_types.setdefault(key, set()).add(
                FeatureType(int(row["feature_type"]))
            )
        except ValueError:
            continue
    return {
        "hydrology": hydrology,
        "affordances": affordances,
        "feature_tags": feature_tags,
        "feature_evidence_tags": feature_evidence_tags,
        "feature_types": feature_types,
    }


def _handoff_payload(
    tile: dict[str, object],
    *,
    transition_type: TransitionType,
    context: dict[str, object],
) -> dict[str, object]:
    x = int(tile["x"])
    y = int(tile["y"])
    key = (x, y)
    hydrology = context["hydrology"]
    if not isinstance(hydrology, dict):
        raise TypeError("Expected hydrology context")
    hydro_row = hydrology.get(key, {})
    if not isinstance(hydro_row, dict):
        hydro_row = {}

    return {
        "cave_type": _cave_type_for(tile, transition_type, context=context),
        "seasonal_state": str(hydro_row.get("seasonal_state", "")),
        "flow_group": int(hydro_row.get("flow_group", 0) or 0),
        "connected_to_underground": bool(
            hydro_row.get("connected_to_underground", False)
        ),
        "substrate": int(tile["substrate"]),
        "elevation_band": int(tile["elevation_band"]),
        "nearby_affordances": _nearby_affordances(key, context=context),
        "handoff_tags": _handoff_tags(tile, transition_type, context=context),
    }


def _transition_evidence_tags(
    tile: dict[str, object],
    *,
    transition_type: TransitionType,
    context: dict[str, object],
) -> tuple[int, ...]:
    key = (int(tile["x"]), int(tile["y"]))
    values: set[int] = set()

    feature_evidence_tags = context.get("feature_evidence_tags")
    if isinstance(feature_evidence_tags, dict):
        evidence = feature_evidence_tags.get(key, set())
        if isinstance(evidence, set):
            values.update(int(value) for value in evidence)

    feature_types = context.get("feature_types")
    if isinstance(feature_types, dict):
        types = feature_types.get(key, set())
        if isinstance(types, set):
            if FeatureType.ORDINARY_CAVE in types:
                values.update(
                    {
                        int(EvidenceTag.PRECURSOR_OCCUPATION),
                        int(EvidenceTag.PRIOR_EXPEDITION),
                    }
                )
            if FeatureType.LAVA_TUBE_SKYLIGHT in types:
                values.update(
                    {
                        int(EvidenceTag.VOLCANIC_BURIAL),
                        int(EvidenceTag.STRUCTURAL_COLLAPSE),
                    }
                )
            if FeatureType.COLLAPSED_LAVA_TUBE in types:
                values.update(
                    {
                        int(EvidenceTag.VOLCANIC_BURIAL),
                        int(EvidenceTag.STRUCTURAL_COLLAPSE),
                        int(EvidenceTag.RECENT_COLLAPSE),
                    }
                )

    if transition_type == TransitionType.PONOR_DESCENT:
        values.update(
            {
                int(EvidenceTag.SUBSIDENCE_DAMAGE),
                int(EvidenceTag.FLOOD_DAMAGE),
            }
        )
    elif transition_type == TransitionType.LAVA_TUBE_SKYLIGHT:
        values.update(
            {
                int(EvidenceTag.VOLCANIC_BURIAL),
                int(EvidenceTag.STRUCTURAL_COLLAPSE),
            }
        )
    elif transition_type == TransitionType.COLLAPSED_LAVA_TUBE:
        values.update(
            {
                int(EvidenceTag.VOLCANIC_BURIAL),
                int(EvidenceTag.STRUCTURAL_COLLAPSE),
                int(EvidenceTag.RECENT_COLLAPSE),
            }
        )
    elif transition_type == TransitionType.SETTLEMENT_ENTRANCE:
        values.update(
            {
                int(EvidenceTag.RECENT_LOCAL_OCCUPATION),
                int(EvidenceTag.REUSED_AS_SHELTER),
            }
        )
    elif transition_type == TransitionType.DOCK_ROUTE:
        values.update(
            {
                int(EvidenceTag.RECENT_LOCAL_OCCUPATION),
                int(EvidenceTag.ROAD_ENGINEERING),
            }
        )
    elif transition_type == TransitionType.TRAIL_EXIT:
        values.add(int(EvidenceTag.MARKED_TRAIL))

    return tuple(sorted(values))


def _cave_type_for(
    tile: dict[str, object],
    transition_type: TransitionType,
    *,
    context: dict[str, object],
) -> str:
    key = (int(tile["x"]), int(tile["y"]))
    feature_types = context["feature_types"]
    if not isinstance(feature_types, dict):
        raise TypeError("Expected feature type context")
    types = feature_types.get(key, set())
    if not isinstance(types, set):
        types = set()
    if FeatureType.ORDINARY_CAVE in types:
        return "ordinary_cave"
    if transition_type == TransitionType.PONOR_DESCENT:
        return "ponor_descent"
    if transition_type == TransitionType.KARST_WINDOW:
        return "karst_window"
    if transition_type == TransitionType.SPRING_SOURCE:
        return "spring_source"
    if transition_type == TransitionType.LAVA_TUBE_SKYLIGHT:
        return "lava_tube_skylight"
    if transition_type == TransitionType.COLLAPSED_LAVA_TUBE:
        return "collapsed_lava_tube"
    if transition_type == TransitionType.CAVE_ENTRANCE:
        if HydroRole(int(tile["hydro_role"])) == HydroRole.KARST_WINDOW:
            return "karst_window"
        if Substrate(int(tile["substrate"])) == Substrate.LIMESTONE:
            return "limestone_cave"
        return "ordinary_cave"
    return ""


def _nearby_affordances(
    key: tuple[int, int],
    *,
    context: dict[str, object],
) -> tuple[str, ...]:
    affordances = context["affordances"]
    if not isinstance(affordances, dict):
        raise TypeError("Expected affordance context")
    x, y = key
    values: set[str] = set()
    for ay in range(y - 2, y + 3):
        for ax in range(x - 2, x + 3):
            nearby = affordances.get((ax, ay), set())
            if isinstance(nearby, set):
                values.update(str(value) for value in nearby)
    return tuple(sorted(values))


def _handoff_tags(
    tile: dict[str, object],
    transition_type: TransitionType,
    *,
    context: dict[str, object],
) -> tuple[str, ...]:
    key = (int(tile["x"]), int(tile["y"]))
    tags = {
        _target_for(transition_type),
        _cave_type_for(tile, transition_type, context=context),
        Biome(int(tile["biome"])).name.lower(),
        Substrate(int(tile["substrate"])).name.lower(),
        ElevationBand(int(tile["elevation_band"])).name.lower(),
    }
    feature_tags = context["feature_tags"]
    if isinstance(feature_tags, dict):
        values = feature_tags.get(key, set())
        if isinstance(values, set):
            tags.update(str(value) for value in values)
    return tuple(sorted(tag for tag in tags if tag))


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

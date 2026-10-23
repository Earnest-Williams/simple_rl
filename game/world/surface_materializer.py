"""Surface chunk materializer: regional promises to concrete tile geometry.

Implements Phase 3 of ``docs/Surface Map Plan.md``. The
:class:`SurfaceMaterializer` expands high-level regional promises
("road", "spring", "harbor", "forest", "ruin") emitted by the region
generator into concrete character-scale tile geometry: materials,
traversal classes, wetness, movement costs, blockers, props, spawn
anchors, hazard anchors, transitions, and the starting player spawn.

Design invariants:

* **Determinism.** Every chunk materializes identically in every process.
  All randomness flows through :class:`~utils.game_rng.GameRNG`, seeded
  from :func:`game.world.surface_chunks.derive_chunk_seed` (chunk-level
  ambient detail) or a per-promise SHA-256 feature seed (template
  geometry). Python ``hash()`` is never used.
* **Seam continuity.** Template geometry is expressed in *global*
  coordinates and clipped per chunk. Feature geometry depends only on
  the promise (never on which chunk renders it), so features spanning
  chunk borders — roads, multi-chunk port footprints — align perfectly at
  seams by construction. Rendering a chunk queries promises overlapping
  its extent, including those anchored in adjacent chunks (the 1-chunk
  boundary buffer).
* **Generator contract.** The promise source supplies regional promises
  per chunk. :class:`InMemoryPromiseSource` is the reference
  implementation and test double; production code can wrap the immutable
  Polars overland maps behind the same :class:`RegionPromiseSource`
  protocol without touching this module.
* **Density caps.** At most one primary structure (harbor, ruin) and
  three minor anchors (springs) materialize per chunk; primary structure
  bounding boxes never exceed 30x30 tiles; ambient debris never covers
  more than 30 percent of the remaining walkable space.

This module deliberately does not own persistence (Phase 4) or actor
hydration (Phase 5); props, spawn anchors, and hazard anchors are carried
on :class:`MaterializedChunk` for those phases to consume.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Any, Final, Protocol, cast

import numpy as np

from common.constants import Material
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from game.world.surface_chunks import (
    DEFAULT_CHUNK_SIZE,
    derive_chunk_seed,
)
from game.world.surface_context import SurfaceSpawnProfile
from utils.game_rng import GameRNG
from worldgen.overland.schema import (
    HydroRole,
    OverlandMapMetadata,
    TraversalClass,
    Wetness,
)

MAX_PRIMARY_STRUCTURES_PER_CHUNK: Final[int] = 1
"""Feature density cap: primary settlement structures per chunk."""

MAX_MINOR_ANCHORS_PER_CHUNK: Final[int] = 3
"""Feature density cap: minor affordance anchors (springs) per chunk."""

MAX_PRIMARY_STRUCTURE_BBOX: Final[tuple[int, int]] = (30, 30)
"""Maximum (width, height) bounding box of a primary structure, in tiles."""

MAX_DEBRIS_FRACTION: Final[float] = 0.30
"""Hard cap: ambient debris coverage of the remaining walkable space."""

DEFAULT_DEBRIS_FRACTION: Final[float] = 0.15
"""Default ambient debris coverage of the remaining walkable space."""

_FEATURE_SEED_MODULUS: Final[int] = 2**32


class SurfaceFeatureKind(IntEnum):
    """Regional promise categories expanded by the materializer."""

    ROAD = auto()
    SPRING = auto()
    HARBOR_PORT = auto()
    FOREST = auto()
    RUIN = auto()


PRIMARY_STRUCTURE_KINDS: Final[frozenset[SurfaceFeatureKind]] = frozenset(
    {SurfaceFeatureKind.HARBOR_PORT, SurfaceFeatureKind.RUIN}
)
"""Feature kinds subject to the one-primary-structure-per-chunk cap."""

MINOR_ANCHOR_KINDS: Final[frozenset[SurfaceFeatureKind]] = frozenset(
    {SurfaceFeatureKind.SPRING}
)
"""Feature kinds subject to the three-minor-anchors-per-chunk cap."""


@dataclass(frozen=True, slots=True)
class RegionalPromise:
    """A generator promise to expand into concrete surface geometry.

    ``anchor_x``/``anchor_y`` are global character-scale tile coordinates.
    Footprint features (harbor, forest, ruin, spring) occupy the global
    rectangle starting at the anchor with size
    ``footprint_chunks * chunk_size`` tiles. Roads carry an orthogonal
    polyline through global ``waypoints``; consecutive waypoints must
    differ in exactly one axis.
    """

    kind: SurfaceFeatureKind
    anchor_x: int
    anchor_y: int
    footprint_chunks: tuple[int, int] = (1, 1)
    waypoints: tuple[tuple[int, int], ...] = ()
    tags: tuple[str, ...] = ()

    def global_rect(
        self, *, chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> tuple[int, int, int, int]:
        """Return the promise's global footprint ``(x0, y0, x1, y1)``.

        ``x1``/``y1`` are exclusive. Roads use the bounding box of their
        waypoint polyline.
        """
        if self.kind == SurfaceFeatureKind.ROAD:
            if len(self.waypoints) < 2:
                raise ValueError(f"Road promise needs at least two waypoints: {self}")
            xs = [point[0] for point in self.waypoints]
            ys = [point[1] for point in self.waypoints]
            return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
        width, height = self.footprint_chunks
        return (
            self.anchor_x,
            self.anchor_y,
            self.anchor_x + width * chunk_size,
            self.anchor_y + height * chunk_size,
        )


class RegionPromiseSource(Protocol):
    """Supplier of regional promises for surface chunks.

    Implementations wrap the immutable regional overland data (Polars or
    otherwise). ``promises_for_chunk`` must return every promise whose
    global footprint overlaps the chunk extent, including promises
    anchored in adjacent chunks, so border features stitch correctly.
    """

    def promises_for_chunk(self, cx: int, cy: int) -> list[RegionalPromise]:
        """Return promises overlapping chunk ``(cx, cy)``."""
        ...

    def base_material_for_chunk(self, cx: int, cy: int) -> Material:
        """Return the ambient base material of chunk ``(cx, cy)``."""
        ...


class InMemoryPromiseSource:
    """Reference promise source holding promises in memory.

    Used by tests and as the template for production adapters over the
    immutable Polars overland maps.
    """

    def __init__(
        self,
        promises: Iterable[RegionalPromise] = (),
        *,
        base_material: Material = Material.GRASS,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self._promises: list[RegionalPromise] = list(promises)
        self._base_material = base_material
        self._chunk_size = chunk_size

    def add(self, promise: RegionalPromise) -> None:
        """Register a promise with the source."""
        self._promises.append(promise)

    def promises_for_chunk(self, cx: int, cy: int) -> list[RegionalPromise]:
        """Return every promise whose global footprint overlaps the chunk."""
        chunk_rect = (
            cx * self._chunk_size,
            cy * self._chunk_size,
            (cx + 1) * self._chunk_size,
            (cy + 1) * self._chunk_size,
        )
        overlapping: list[RegionalPromise] = []
        for promise in self._promises:
            if promise.kind == SurfaceFeatureKind.SPRING:
                rect = (
                    promise.anchor_x - 3,
                    promise.anchor_y - 3,
                    promise.anchor_x + 4,
                    promise.anchor_y + 4,
                )
            elif self._promise_kind_needs_geometry(promise):
                rect = promise.global_rect(chunk_size=self._chunk_size)
            else:
                rect = (
                    promise.anchor_x,
                    promise.anchor_y,
                    promise.anchor_x + 1,
                    promise.anchor_y + 1,
                )
            if self._rects_overlap(rect, chunk_rect):
                overlapping.append(promise)
        return overlapping

    def base_material_for_chunk(self, cx: int, cy: int) -> Material:
        """Return the configured ambient base material."""
        return self._base_material

    @staticmethod
    def _promise_kind_needs_geometry(promise: RegionalPromise) -> bool:
        return promise.kind in (
            SurfaceFeatureKind.ROAD,
            SurfaceFeatureKind.HARBOR_PORT,
            SurfaceFeatureKind.FOREST,
            SurfaceFeatureKind.RUIN,
        )

    @staticmethod
    def _rects_overlap(
        a: tuple[int, int, int, int], b: tuple[int, int, int, int]
    ) -> bool:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


@dataclass(frozen=True, slots=True)
class SurfaceProp:
    """A concrete prop placed by a materialization template."""

    x: int
    y: int
    kind: str
    material: Material
    blocks_movement: bool = False
    blocks_sight: bool = False
    destructible: bool = False


@dataclass(frozen=True, slots=True)
class SurfaceSpawnAnchor:
    """A concrete entity spawn anchor in global coordinates."""

    profile: SurfaceSpawnProfile
    x: int
    y: int
    note: str = ""


@dataclass(frozen=True, slots=True)
class SurfaceHazardAnchor:
    """A hazard anchor (trap or monster spawner) in global coordinates."""

    x: int
    y: int
    kind: str


class _ChunkCanvas:
    """Mutable chunk-local drawing surface with global-coordinate clipping.

    Template code paints in global coordinates; writes outside the chunk
    extent are ignored. This is what makes multi-chunk features render
    seam-perfectly: the same global geometry is drawn by every chunk it
    intersects.
    """

    def __init__(
        self,
        cx: int,
        cy: int,
        cz: int,
        chunk_size: int,
        base_material: Material,
    ) -> None:
        size = (chunk_size, chunk_size)
        self.cx = cx
        self.cy = cy
        self.cz = cz
        self.chunk_size = chunk_size
        self.origin_x = cx * chunk_size
        self.origin_y = cy * chunk_size
        self.base_material = base_material
        self.materials: np.ndarray = np.full(size, int(base_material), dtype=np.int16)
        self.traversal: np.ndarray = np.full(
            size, int(TraversalClass.NORMAL), dtype=np.int16
        )
        self.wetness: np.ndarray = np.full(size, int(Wetness.DRY), dtype=np.int16)
        self.hydro: np.ndarray = np.full(size, int(HydroRole.NONE), dtype=np.int16)
        self.movement_cost: np.ndarray = np.ones(size, dtype=np.float32)
        self.blocked: np.ndarray = np.zeros(size, dtype=bool)
        self.ceiling: np.ndarray = np.zeros(size, dtype=np.int16)
        self.painted: np.ndarray = np.zeros(size, dtype=bool)
        self.props: list[SurfaceProp] = []
        self.spawn_anchors: list[SurfaceSpawnAnchor] = []
        self.hazard_anchors: list[SurfaceHazardAnchor] = []
        self.transitions: dict[tuple[int, int], list[dict[str, Any]]] = {}
        self.affordances: dict[tuple[int, int], list[dict[str, Any]]] = {}
        self.player_start: tuple[int, int] | None = None
        self.stats: dict[str, int] = {
            "primary_structures": 0,
            "minor_anchors": 0,
            "roads": 0,
            "ambient_features": 0,
            "props": 0,
            "spawn_anchors": 0,
            "hazard_anchors": 0,
            "debris": 0,
            "walkable": 0,
        }

    def local(self, gx: int, gy: int) -> tuple[int, int] | None:
        """Return chunk-local coordinates for a global tile, or ``None``."""
        lx = gx - self.origin_x
        ly = gy - self.origin_y
        if 0 <= lx < self.chunk_size and 0 <= ly < self.chunk_size:
            return (lx, ly)
        return None

    def paint(
        self,
        gx: int,
        gy: int,
        *,
        material: Material | None = None,
        traversal: TraversalClass | None = None,
        wetness: Wetness | None = None,
        hydro: HydroRole | None = None,
        cost: float | None = None,
        blocked: bool | None = None,
        ceiling: int | None = None,
    ) -> None:
        """Write tile properties at global ``(gx, gy)`` if inside the chunk."""
        local = self.local(gx, gy)
        if local is None:
            return
        lx, ly = local
        if material is not None:
            self.materials[ly, lx] = int(material)
        if traversal is not None:
            self.traversal[ly, lx] = int(traversal)
        if wetness is not None:
            self.wetness[ly, lx] = int(wetness)
        if hydro is not None:
            self.hydro[ly, lx] = int(hydro)
        if cost is not None:
            self.movement_cost[ly, lx] = np.float32(cost)
        if blocked is not None:
            self.blocked[ly, lx] = bool(blocked)
        if ceiling is not None:
            self.ceiling[ly, lx] = np.int16(ceiling)
        self.painted[ly, lx] = True

    def add_prop(self, prop: SurfaceProp) -> None:
        """Attach a prop located inside this chunk."""
        if self.local(prop.x, prop.y) is not None:
            self.props.append(prop)

    def add_spawn_anchor(self, anchor: SurfaceSpawnAnchor) -> None:
        """Attach a spawn anchor located inside this chunk."""
        if self.local(anchor.x, anchor.y) is not None:
            self.spawn_anchors.append(anchor)

    def add_hazard_anchor(self, anchor: SurfaceHazardAnchor) -> None:
        """Attach a hazard anchor located inside this chunk."""
        if self.local(anchor.x, anchor.y) is not None:
            self.hazard_anchors.append(anchor)

    def add_transition(self, gx: int, gy: int, payload: dict[str, Any]) -> None:
        """Register a transition payload at global ``(gx, gy)``."""
        if self.local(gx, gy) is not None:
            self.transitions.setdefault((gx, gy), []).append(payload)

    def add_affordance(self, gx: int, gy: int, payload: dict[str, Any]) -> None:
        """Register an affordance payload at global ``(gx, gy)``."""
        if self.local(gx, gy) is not None:
            self.affordances.setdefault((gx, gy), []).append(payload)

    def freeze(self) -> MaterializedChunk:
        """Return the immutable materialization result for this chunk."""
        self.stats["props"] = len(self.props)
        self.stats["spawn_anchors"] = len(self.spawn_anchors)
        self.stats["hazard_anchors"] = len(self.hazard_anchors)
        self.stats["walkable"] = int(np.count_nonzero(~self.blocked))
        return MaterializedChunk(
            cx=self.cx,
            cy=self.cy,
            cz=self.cz,
            chunk_size=self.chunk_size,
            materials=self.materials,
            traversal=self.traversal,
            wetness=self.wetness,
            hydro=self.hydro,
            movement_cost=self.movement_cost,
            blocked=self.blocked,
            ceiling=self.ceiling,
            props=list(self.props),
            spawn_anchors=list(self.spawn_anchors),
            hazard_anchors=list(self.hazard_anchors),
            transitions={key: list(rows) for key, rows in self.transitions.items()},
            affordances={key: list(rows) for key, rows in self.affordances.items()},
            player_start=self.player_start,
            stats=dict(self.stats),
        )


@dataclass(frozen=True, slots=True)
class MaterializedChunk:
    """Concrete tile geometry for one surface chunk.

    Grids are chunk-local ``(y, x)`` arrays of shape
    ``(chunk_size, chunk_size)``; anchors, props, transitions, and
    affordances use global character-scale coordinates. ``origin_x`` and
    ``origin_y`` are the global coordinates of local ``(0, 0)``.
    """

    cx: int
    cy: int
    cz: int
    chunk_size: int
    materials: np.ndarray
    traversal: np.ndarray
    wetness: np.ndarray
    hydro: np.ndarray
    movement_cost: np.ndarray
    blocked: np.ndarray
    ceiling: np.ndarray
    props: list[SurfaceProp]
    spawn_anchors: list[SurfaceSpawnAnchor]
    hazard_anchors: list[SurfaceHazardAnchor]
    transitions: dict[tuple[int, int], list[dict[str, Any]]]
    affordances: dict[tuple[int, int], list[dict[str, Any]]]
    player_start: tuple[int, int] | None
    stats: dict[str, int]

    @property
    def origin_x(self) -> int:
        """Global x coordinate of chunk-local x 0."""
        return self.cx * self.chunk_size

    @property
    def origin_y(self) -> int:
        """Global y coordinate of chunk-local y 0."""
        return self.cy * self.chunk_size


class SurfaceMaterializer:
    """Expands regional promises into concrete surface chunk geometry."""

    def __init__(
        self,
        promise_source: RegionPromiseSource,
        *,
        world_seed: int | str,
        content_version: int = 1,
        generation_version: int = 1,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        debris_fraction: float = DEFAULT_DEBRIS_FRACTION,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be a positive integer, got {chunk_size}")
        if not 0.0 <= debris_fraction <= MAX_DEBRIS_FRACTION:
            raise ValueError(
                f"debris_fraction must be in [0.0, {MAX_DEBRIS_FRACTION}], "
                f"got {debris_fraction}"
            )
        self._promise_source = promise_source
        self._world_seed = world_seed
        self._content_version = content_version
        self._generation_version = generation_version
        self._chunk_size = chunk_size
        self._debris_fraction = debris_fraction

    @property
    def chunk_size(self) -> int:
        """Configured chunk dimension ``S_c`` in tiles."""
        return self._chunk_size

    def materialize_chunk(self, cx: int, cy: int, cz: int = 0) -> MaterializedChunk:
        """Materialize chunk ``(cx, cy, cz)`` deterministically.

        Queries the promise source for every promise overlapping the
        chunk (the 1-chunk boundary buffer), enforces the feature density
        caps, expands templates in global coordinates, and clips to the
        chunk extent.
        """
        chunk_seed = derive_chunk_seed(
            self._world_seed,
            cx,
            cy,
            cz,
            content_version=self._content_version,
            generation_version=self._generation_version,
        )
        chunk_rng = GameRNG(seed=chunk_seed)
        canvas = _ChunkCanvas(
            cx,
            cy,
            cz,
            self._chunk_size,
            self._promise_source.base_material_for_chunk(cx, cy),
        )
        promises = self._select_promises(
            self._promise_source.promises_for_chunk(cx, cy)
        )
        for promise in promises[SurfaceFeatureKind.FOREST]:
            self._expand_forest(canvas, promise)
            canvas.stats["ambient_features"] += 1
        for promise in promises[SurfaceFeatureKind.ROAD]:
            self._expand_road(canvas, promise)
            canvas.stats["roads"] += 1
        for promise in promises[SurfaceFeatureKind.SPRING]:
            self._expand_spring(canvas, promise)
            canvas.stats["minor_anchors"] += 1
        for kind in (SurfaceFeatureKind.HARBOR_PORT, SurfaceFeatureKind.RUIN):
            for promise in promises[kind]:
                if kind == SurfaceFeatureKind.HARBOR_PORT:
                    self._expand_harbor(canvas, promise)
                else:
                    self._expand_ruin(canvas, promise)
                canvas.stats["primary_structures"] += 1
        self._scatter_debris(canvas, chunk_rng)
        return canvas.freeze()

    def chunk_seed_for(self, cx: int, cy: int, cz: int = 0) -> int:
        """Return the derived RNG seed for chunk ``(cx, cy, cz)``."""
        return derive_chunk_seed(
            self._world_seed,
            cx,
            cy,
            cz,
            content_version=self._content_version,
            generation_version=self._generation_version,
        )

    def _select_promises(
        self, overlapping: list[RegionalPromise]
    ) -> dict[SurfaceFeatureKind, list[RegionalPromise]]:
        """Apply anchor-owner density caps before clipping neighboring features.

        An anchor is selected or rejected by exactly one chunk: the chunk
        containing its global anchor. Neighbor chunks replay that decision
        rather than counting a bleeding footprint against their own cap.
        """
        capped = PRIMARY_STRUCTURE_KINDS | MINOR_ANCHOR_KINDS
        selected: dict[SurfaceFeatureKind, list[RegionalPromise]] = {
            kind: [] for kind in SurfaceFeatureKind
        }
        owner_cache: dict[tuple[int, int], set[RegionalPromise]] = {}

        def order_key(
            promise: RegionalPromise,
        ) -> tuple[int, int, int, tuple[int, int]]:
            return (
                promise.kind.value,
                promise.anchor_x,
                promise.anchor_y,
                promise.footprint_chunks,
            )

        for promise in sorted(overlapping, key=order_key):
            if promise.kind not in capped:
                selected[promise.kind].append(promise)
                continue
            owner = (
                promise.anchor_x // self._chunk_size,
                promise.anchor_y // self._chunk_size,
            )
            if owner not in owner_cache:
                locally_owned = sorted(
                    (
                        candidate
                        for candidate in self._promise_source.promises_for_chunk(*owner)
                        if candidate.kind in capped
                        and candidate.anchor_x // self._chunk_size == owner[0]
                        and candidate.anchor_y // self._chunk_size == owner[1]
                    ),
                    key=order_key,
                )
                approved: set[RegionalPromise] = set()
                primary = 0
                minor = 0
                for candidate in locally_owned:
                    if candidate.kind in PRIMARY_STRUCTURE_KINDS:
                        if primary >= MAX_PRIMARY_STRUCTURES_PER_CHUNK:
                            continue
                        primary += 1
                    else:
                        if minor >= MAX_MINOR_ANCHORS_PER_CHUNK:
                            continue
                        minor += 1
                    approved.add(candidate)
                owner_cache[owner] = approved
            if promise in owner_cache[owner]:
                selected[promise.kind].append(promise)
        return selected

    def _feature_rng(self, promise: RegionalPromise) -> GameRNG:
        """Return the per-promise RNG shared by every chunk it touches.

        The seed is a pure function of the promise identity, so template
        geometry consumes identical randomness no matter which chunk
        clips it; border features therefore stitch by construction.
        """
        key = (
            f"{self._world_seed}:{promise.kind.name}"
            f":{promise.anchor_x}:{promise.anchor_y}"
            f":{promise.footprint_chunks[0]}:{promise.footprint_chunks[1]}"
        )
        seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
        return GameRNG(seed=seed % _FEATURE_SEED_MODULUS)

    def _expand_road(self, canvas: _ChunkCanvas, promise: RegionalPromise) -> None:
        """Expand a road promise: paving, shoulders, ruts, and weeds.

        The center line is paved ``Material.ROAD`` with ``TRACK`` ruts
        worn into the wheel lines, flanked by gravel shoulders that
        retain footprints, with sparse encroaching weeds.
        """
        rng = self._feature_rng(promise)
        waypoints = promise.waypoints
        for index in range(len(waypoints) - 1):
            x0, y0 = waypoints[index]
            x1, y1 = waypoints[index + 1]
            if x0 != x1 and y0 != y1:
                raise ValueError(f"Road waypoints must be orthogonal: {waypoints}")
            dx = (x1 > x0) - (x1 < x0)
            dy = (y1 > y0) - (y1 < y0)
            steps = abs(x1 - x0) + abs(y1 - y0)
            for step in range(steps + (1 if index == 0 else 0)):
                cx_ = x0 + dx * step
                cy_ = y0 + dy * step
                # Wheel ruts: the off-center paving lines wear to gravel,
                # which retains tracks.
                for offset in (-1, 1):
                    if rng.get_float() < 0.30:
                        rut_material = Material.GRAVEL
                    else:
                        rut_material = Material.ROAD
                    canvas.paint(
                        cx_ + (offset if dy else 0),
                        cy_ + (offset if dx else 0),
                        material=rut_material,
                        traversal=TraversalClass.NORMAL,
                        wetness=Wetness.DRY,
                        cost=0.75,
                        blocked=False,
                    )
                canvas.paint(
                    cx_,
                    cy_,
                    material=Material.ROAD,
                    traversal=TraversalClass.NORMAL,
                    wetness=Wetness.DRY,
                    cost=0.75,
                    blocked=False,
                )
                # Gravel shoulders with sparse encroaching weeds.
                for offset in (-2, 2):
                    shoulder_material: Material
                    if rng.get_float() < 0.10:
                        shoulder_material = Material.GRASS
                    else:
                        shoulder_material = Material.GRAVEL
                    canvas.paint(
                        cx_ + (offset if dy else 0),
                        cy_ + (offset if dx else 0),
                        material=shoulder_material,
                        traversal=TraversalClass.NORMAL,
                        wetness=Wetness.DRY,
                        cost=1.0,
                        blocked=False,
                    )

    def _expand_spring(self, canvas: _ChunkCanvas, promise: RegionalPromise) -> None:
        """Expand a spring promise into water, banks, and reed beds.

        The center is swim-only deep water ringed by muddy banks, reed
        beds that block line of sight, and a wildlife spawn anchor with
        a spring-refuge affordance.
        """
        rng = self._feature_rng(promise)
        anchor_x, anchor_y = promise.anchor_x, promise.anchor_y
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                distance = max(abs(dx), abs(dy))
                x = anchor_x + dx
                y = anchor_y + dy
                if distance <= 1:
                    canvas.paint(
                        x,
                        y,
                        material=Material.DEEP_WATER,
                        traversal=TraversalClass.SWIM_OR_BOAT,
                        wetness=Wetness.DEEP_FLOODED,
                        hydro=HydroRole.SPRING,
                        cost=1.5,
                        blocked=False,
                    )
                elif distance == 2:
                    canvas.paint(
                        x,
                        y,
                        material=Material.MUD,
                        traversal=TraversalClass.WADE,
                        wetness=Wetness.SATURATED,
                        cost=1.25,
                        blocked=False,
                    )
                else:
                    is_reed = rng.get_float() < 0.5
                    material = Material.REEDBED if is_reed else Material.MUDFLAT
                    canvas.paint(
                        x,
                        y,
                        material=material,
                        traversal=TraversalClass.SLOW,
                        wetness=Wetness.WET,
                        cost=1.25,
                        blocked=False,
                    )
                    if is_reed:
                        canvas.add_prop(
                            SurfaceProp(
                                x=x,
                                y=y,
                                kind="reeds",
                                material=Material.REEDBED,
                                blocks_sight=True,
                            )
                        )
                        if not canvas.affordances:
                            canvas.add_affordance(
                                x,
                                y,
                                {"affordance": "spring_refuge"},
                            )
        canvas.add_spawn_anchor(
            SurfaceSpawnAnchor(
                profile=SurfaceSpawnProfile.WATER_WILDLIFE,
                x=anchor_x,
                y=anchor_y + 2,
                note="spring bank",
            )
        )

    def _expand_harbor(self, canvas: _ChunkCanvas, promise: RegionalPromise) -> None:
        """Expand a harbor/port promise across its footprint chunks.

        Wooden boardwalk and stone docks line the water side, a built
        platform holds crates and rope props, and the starting player
        spawn and dock-route transition are resolved into geometry.
        """
        rng = self._feature_rng(promise)
        width_chunks, height_chunks = promise.footprint_chunks
        x0, y0 = promise.anchor_x, promise.anchor_y
        x1 = x0 + width_chunks * self._chunk_size
        y1 = y0 + height_chunks * self._chunk_size
        # Dock band: boardwalk along the west (water-facing) edge, then
        # stone dock planking.
        for y in range(y0, y1):
            canvas.paint(x0, y, material=Material.BOARDWALK, cost=1.0)
            for dx in (1, 2):
                canvas.paint(x0 + dx, y, material=Material.DOCK, cost=1.0)
        for y in range(y0, y1):
            for x in range(x0 + 3, x1):
                canvas.paint(
                    x,
                    y,
                    material=Material.BUILDING_FLOOR,
                    traversal=TraversalClass.NORMAL,
                    wetness=Wetness.DRY,
                    cost=1.0,
                    blocked=False,
                )
        start_x = x0 + (x1 - x0) // 2
        start_y = y0 + (y1 - y0) // 2
        canvas.paint(
            start_x,
            start_y,
            material=Material.BUILDING_FLOOR,
            blocked=False,
        )
        canvas.player_start = (start_x, start_y)
        canvas.add_spawn_anchor(
            SurfaceSpawnAnchor(
                profile=SurfaceSpawnProfile.HUMAN_SETTLEMENT,
                x=start_x,
                y=start_y,
                note="harbor start",
            )
        )
        canvas.add_transition(
            x0,
            y0 + (y1 - y0) // 2,
            {"transition_type": "dock_route"},
        )
        # Crates (destructible containers) and rope props. Positions are
        # drawn from the feature RNG in a fixed order so every chunk in
        # the footprint agrees on them.
        for _ in range(8):
            crate_x = rng.get_int(x0 + 3, x1 - 1)
            crate_y = rng.get_int(y0, y1 - 1)
            if (crate_x, crate_y) == (start_x, start_y):
                continue
            canvas.paint(crate_x, crate_y, blocked=True)
            canvas.add_prop(
                SurfaceProp(
                    x=crate_x,
                    y=crate_y,
                    kind="crate",
                    material=Material.WOOD_WALL,
                    blocks_movement=True,
                    destructible=True,
                )
            )
        for _ in range(4):
            rope_x = rng.get_int(x0, min(x0 + 2, x1 - 1))
            rope_y = rng.get_int(y0, y1 - 1)
            canvas.add_prop(
                SurfaceProp(
                    x=rope_x,
                    y=rope_y,
                    kind="rope",
                    material=Material.BOARDWALK,
                )
            )

    def _expand_forest(self, canvas: _ChunkCanvas, promise: RegionalPromise) -> None:
        """Expand a forest promise into floor, trees, and forage nodes."""
        rng = self._feature_rng(promise)
        width_chunks, height_chunks = promise.footprint_chunks
        x0, y0 = promise.anchor_x, promise.anchor_y
        x1 = x0 + width_chunks * self._chunk_size
        y1 = y0 + height_chunks * self._chunk_size
        tree_tiles: list[tuple[int, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                roll = rng.get_float()
                if roll < 0.25:
                    canvas.paint(
                        x,
                        y,
                        material=Material.FOREST_FLOOR,
                        blocked=True,
                        cost=1.0,
                    )
                    canvas.add_prop(
                        SurfaceProp(
                            x=x,
                            y=y,
                            kind="tree",
                            material=Material.FOREST_FLOOR,
                            blocks_movement=True,
                            blocks_sight=True,
                        )
                    )
                    tree_tiles.append((x, y))
                elif roll < 0.45:
                    canvas.paint(
                        x,
                        y,
                        material=Material.FERN_UNDERSTORY,
                        traversal=TraversalClass.SLOW,
                        cost=1.25,
                        blocked=False,
                    )
                else:
                    canvas.paint(
                        x,
                        y,
                        material=Material.FOREST_FLOOR,
                        traversal=TraversalClass.NORMAL,
                        cost=1.0,
                        blocked=False,
                    )
        # Fallen logs.
        for _ in range(3):
            log_x = rng.get_int(x0, x1 - 1)
            log_y = rng.get_int(y0, y1 - 1)
            canvas.paint(log_x, log_y, blocked=True)
            canvas.add_prop(
                SurfaceProp(
                    x=log_x,
                    y=log_y,
                    kind="fallen_log",
                    material=Material.FOREST_FLOOR,
                    blocks_movement=True,
                )
            )
        # Forage nodes and wildlife anchors on non-blocked floor tiles.
        placed_anchors = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                if placed_anchors >= 2:
                    break
                local = canvas.local(x, y)
                if local is None:
                    continue
                lx, ly = local
                if (
                    not canvas.blocked[ly, lx]
                    and canvas.materials[ly, lx] == int(Material.FOREST_FLOOR)
                    and rng.get_float() < 0.10
                ):
                    canvas.add_affordance(x, y, {"affordance": "forage"})
                    canvas.add_spawn_anchor(
                        SurfaceSpawnAnchor(
                            profile=SurfaceSpawnProfile.FORAGE_WILDLIFE,
                            x=x,
                            y=y,
                            note="forage node",
                        )
                    )
                    placed_anchors += 1

    def _expand_ruin(self, canvas: _ChunkCanvas, promise: RegionalPromise) -> None:
        """Expand a ruin promise into walls, doors, loot, and hazards."""
        rng = self._feature_rng(promise)
        width = 20 + rng.get_int(0, MAX_PRIMARY_STRUCTURE_BBOX[0] - 20)
        height = 20 + rng.get_int(0, MAX_PRIMARY_STRUCTURE_BBOX[1] - 20)
        x0, y0 = promise.anchor_x, promise.anchor_y
        x1 = x0 + width
        y1 = y0 + height
        # Interior flagstone floors.
        for y in range(y0, y1):
            for x in range(x0, x1):
                canvas.paint(
                    x,
                    y,
                    material=Material.RUIN_FLOOR,
                    traversal=TraversalClass.NORMAL,
                    wetness=Wetness.DRY,
                    cost=1.0,
                    blocked=False,
                )
        # Crumbling perimeter walls with deterministic gaps, plus a
        # locked iron door centered on the north wall.
        door_x = x0 + width // 2
        door_y = y0
        for y in range(y0, y1):
            for x in range(x0, x1):
                if x not in (x0, x1 - 1) and y not in (y0, y1 - 1):
                    continue
                if (x, y) == (door_x, door_y):
                    canvas.paint(
                        x,
                        y,
                        material=Material.DOOR_CLOSED,
                        traversal=TraversalClass.BLOCKED,
                        cost=float("inf"),
                        blocked=True,
                    )
                    canvas.add_prop(
                        SurfaceProp(
                            x=x,
                            y=y,
                            kind="iron_door",
                            material=Material.DOOR_CLOSED,
                            blocks_movement=True,
                            blocks_sight=True,
                        )
                    )
                elif rng.get_float() < 0.15:
                    continue  # Collapsed gap in the wall.
                else:
                    canvas.paint(
                        x,
                        y,
                        material=Material.RUIN_WALL,
                        traversal=TraversalClass.BLOCKED,
                        cost=float("inf"),
                        blocked=True,
                    )
        # Basalt rubble patches.
        for _ in range(6):
            rubble_x = rng.get_int(x0 + 1, x1 - 2)
            rubble_y = rng.get_int(y0 + 1, y1 - 2)
            canvas.paint(
                rubble_x,
                rubble_y,
                material=Material.SCREE,
                traversal=TraversalClass.SLOW,
                cost=1.25,
                blocked=False,
            )
        # Chests and hazard anchors (traps, monster spawners).
        for _ in range(2):
            chest_x = rng.get_int(x0 + 1, x1 - 2)
            chest_y = rng.get_int(y0 + 1, y1 - 2)
            canvas.paint(chest_x, chest_y, blocked=True)
            canvas.add_prop(
                SurfaceProp(
                    x=chest_x,
                    y=chest_y,
                    kind="chest",
                    material=Material.WOOD_WALL,
                    blocks_movement=True,
                    destructible=True,
                )
            )
        hazard_kinds = ("trap", "monster_spawner")
        for hazard_kind in hazard_kinds:
            hazard_x = rng.get_int(x0 + 1, x1 - 2)
            hazard_y = rng.get_int(y0 + 1, y1 - 2)
            canvas.add_hazard_anchor(
                SurfaceHazardAnchor(x=hazard_x, y=hazard_y, kind=hazard_kind)
            )

    def _scatter_debris(self, canvas: _ChunkCanvas, chunk_rng: GameRNG) -> None:
        """Scatter ambient debris over untouched base terrain.

        Uses the chunk-local RNG (ambient detail may differ per chunk)
        and only paints tiles no template touched. Coverage never
        exceeds ``MAX_DEBRIS_FRACTION`` of the remaining walkable space.
        """
        candidates: list[tuple[int, int]] = []
        for ly in range(canvas.chunk_size):
            for lx in range(canvas.chunk_size):
                if not canvas.painted[ly, lx] and not canvas.blocked[ly, lx]:
                    candidates.append((lx, ly))
        if not candidates:
            return
        target = int(len(candidates) * self._debris_fraction)
        placed = 0
        for lx, ly in candidates:
            if placed >= target:
                break
            if chunk_rng.get_float() >= self._debris_fraction:
                continue
            gx = canvas.origin_x + lx
            gy = canvas.origin_y + ly
            roll = chunk_rng.get_float()
            if roll < 0.50:
                canvas.paint(
                    gx,
                    gy,
                    material=canvas.base_material,
                    blocked=True,
                )
                canvas.add_prop(
                    SurfaceProp(
                        x=gx,
                        y=gy,
                        kind="tree",
                        material=canvas.base_material,
                        blocks_movement=True,
                        blocks_sight=True,
                    )
                )
            elif roll < 0.75:
                canvas.paint(
                    gx,
                    gy,
                    material=Material.SCREE,
                    traversal=TraversalClass.SLOW,
                    cost=1.25,
                    blocked=True,
                )
                canvas.add_prop(
                    SurfaceProp(
                        x=gx,
                        y=gy,
                        kind="rock",
                        material=Material.SCREE,
                        blocks_movement=True,
                    )
                )
            else:
                canvas.paint(
                    gx,
                    gy,
                    material=Material.MUDFLAT,
                    traversal=TraversalClass.WADE,
                    wetness=Wetness.WET,
                    cost=1.25,
                    blocked=False,
                )
            placed += 1
        canvas.stats["debris"] = placed


def ensure_surface_metadata(game_map: GameMap) -> OverlandMapMetadata:
    """Return the map's overland sidecar, creating a default if absent.

    The default sidecar carries grass terrain with normal traversal so
    viewport assembly can write chunk geometry into it.
    """
    metadata = game_map.overland_metadata
    if metadata is not None:
        return cast(OverlandMapMetadata, metadata)
    height, width = game_map.tiles.shape
    metadata = OverlandMapMetadata(
        material_grid=np.full((height, width), int(Material.GRASS), dtype=np.int16),
        biome_grid=np.zeros((height, width), dtype=np.int16),
        hydro_grid=np.full((height, width), int(HydroRole.NONE), dtype=np.int16),
        wetness_grid=np.full((height, width), int(Wetness.DRY), dtype=np.int16),
        movement_cost_grid=np.ones((height, width), dtype=np.float32),
        traversal_class_grid=np.full(
            (height, width), int(TraversalClass.NORMAL), dtype=np.int16
        ),
        route_segments=[],
        evidence_tags={},
        transitions={},
        affordances={},
        starting_contract={},
    )
    game_map.overland_metadata = metadata
    return metadata


def apply_materialized_chunk(
    game_map: GameMap,
    materialized: MaterializedChunk,
    *,
    viewport_origin_x: int = 0,
    viewport_origin_y: int = 0,
) -> None:
    """Write a materialized chunk into a viewport ``GameMap``.

    ``viewport_origin_x``/``viewport_origin_y`` are the global
    coordinates of the viewport's ``(0, 0)`` tile, so multi-chunk viewports
    (e.g. the 3x3 first-playable area) assemble by applying each chunk
    with the same viewport origin. Tile geometry, sidecar grids,
    transitions, affordances, and the player start contract are written;
    props, spawn anchors, and hazard anchors stay on the
    :class:`MaterializedChunk` for persistence (Phase 4) and entity
    hydration (Phase 5) to consume.
    """
    metadata = ensure_surface_metadata(game_map)
    size = materialized.chunk_size
    offset_x = materialized.origin_x - viewport_origin_x
    offset_y = materialized.origin_y - viewport_origin_y
    if (
        offset_x < 0
        or offset_y < 0
        or offset_x + size > game_map.width
        or offset_y + size > game_map.height
    ):
        raise ValueError(
            f"Chunk {materialized.cx},{materialized.cy} does not fit the "
            f"viewport at offset ({offset_x}, {offset_y})"
        )
    tiles = np.where(materialized.blocked, TILE_ID_WALL, TILE_ID_FLOOR).astype(np.uint8)
    game_map.tiles[offset_y : offset_y + size, offset_x : offset_x + size] = tiles
    game_map.ceiling_map[offset_y : offset_y + size, offset_x : offset_x + size] = (
        materialized.ceiling
    )
    metadata.material_grid[offset_y : offset_y + size, offset_x : offset_x + size] = (
        materialized.materials
    )
    metadata.traversal_class_grid[
        offset_y : offset_y + size, offset_x : offset_x + size
    ] = materialized.traversal
    metadata.wetness_grid[offset_y : offset_y + size, offset_x : offset_x + size] = (
        materialized.wetness
    )
    metadata.hydro_grid[offset_y : offset_y + size, offset_x : offset_x + size] = (
        materialized.hydro
    )
    metadata.movement_cost_grid[
        offset_y : offset_y + size, offset_x : offset_x + size
    ] = materialized.movement_cost
    # Replace, rather than extend, per-tile metadata on re-application.
    for mapping, incoming in (
        (metadata.transitions, materialized.transitions),
        (metadata.affordances, materialized.affordances),
    ):
        for key in list(mapping):
            if (
                materialized.origin_x <= key[0] < materialized.origin_x + size
                and materialized.origin_y <= key[1] < materialized.origin_y + size
            ):
                del mapping[key]
        for coordinate, rows in incoming.items():
            mapping[coordinate] = list(rows)
    if materialized.player_start is not None:
        metadata.starting_contract["player_start"] = [
            materialized.player_start[0],
            materialized.player_start[1],
        ]
    game_map.update_tile_transparency()


__all__ = [
    "DEFAULT_DEBRIS_FRACTION",
    "InMemoryPromiseSource",
    "MaterializedChunk",
    "MAX_DEBRIS_FRACTION",
    "MAX_MINOR_ANCHORS_PER_CHUNK",
    "MAX_PRIMARY_STRUCTURES_PER_CHUNK",
    "MAX_PRIMARY_STRUCTURE_BBOX",
    "MINOR_ANCHOR_KINDS",
    "PRIMARY_STRUCTURE_KINDS",
    "RegionPromiseSource",
    "RegionalPromise",
    "SurfaceFeatureKind",
    "SurfaceHazardAnchor",
    "SurfaceMaterializer",
    "SurfaceProp",
    "SurfaceSpawnAnchor",
    "apply_materialized_chunk",
    "ensure_surface_metadata",
]

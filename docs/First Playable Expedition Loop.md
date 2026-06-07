# First Playable Expedition Loop

## Status

This document is the current implementation plan for turning the existing overland, starting port, route, blockage, and cave-transition systems into a small playable vertical slice.

This is not a broad design document. It is an execution plan. Decisions here are intentionally explicit so humans and LLM agents stay on-task. These decisions can be changed later, but until this document is updated, treat them as binding for first-playable work.

Status: the first-playable slice is now wired through `python tools/play_game.py --first-playable` and covered by `tests/test_first_playable_expedition.py` plus `tests/integration/test_first_playable_launcher.py`.

## Goal

Build one complete playable expedition loop:

```text
ruined harbor / starting port
  -> survey nearby area
  -> identify road, resources, blockage, cave, and inland objective
  -> follow visible route inland
  -> handle one clearable blockage
  -> enter one cave-like transition
  -> survive one cave room
  -> return to port with a discovery
  -> show loop-complete state
```

The target is not a finished game. The target is a coherent 10-minute playable spine that proves the current worldgen, overland UI, runtime map metadata, movement, route semantics, and cave handoff can work together.

The current project state now implements this direction: the main game engine is integrated, and the first-playable launch path, overland starting-region contract, route reveal, blockage repair, cave handoff, and return-to-port completion are wired together with focused tests.

## Source-of-truth context

The overland generator is already the primary terrain contract for the surface world. It describes semantic terrain first, then derives gameplay behavior from that terrain. The implemented design rule is:

```text
material + wetness + surface_flags -> traversal and gameplay behavior
```

This matters because the playable loop should consume overland semantics instead of inventing a parallel map format. 

The first playable target should be one dense starting region, not the full continent. The overland roadmap already defines this starting region as containing a ruined harbor, survey zone, fresh water, resources, ancient road, clearable blockage, waystation candidate, inland site, ordinary cave, and at least one meaningful cave transition. 

The implemented overland contract already emits most of that shape: ruined harbor, local survey zone, fresh water/resource sites, ancient road, clearable blockage, waystation candidate, inland site, ordinary cave, route metadata, and actor-profile cost hints. 

Therefore the remaining work is polish and expansion, not basic runtime gameplay binding.

---

# Hard decisions

## D1. The first playable loop starts at the ruined harbor / merged starting port

The player starts on or adjacent to the dock/harbor surface produced by the merged starting port flow.

Use the documented overland settlement merge path:

```python
starting_port_from_overland(overland)
merge_settlement_into_overland(overland, settlement, origin=origin)
```

The merged settlement surface may contain roads, docks, buildings, walls, bridges, fields, orchards, and pastures. 

Do not create a separate handcrafted tutorial map for the first loop. If a fallback is needed for tests, keep it tiny and clearly marked as a fixture, not the production start.

## D2. The first survey command is not a knowledge system

Add one lightweight survey command.

The survey command reveals nearby overland metadata and creates a small set of visible objectives. It does not implement fog-of-war memory, rumor propagation, archaeology inference, faction knowledge, map annotation editing, journal prose, or long-term expedition records.

The roadmap explicitly treats survey, map knowledge, expedition logs, and related systems as downstream consumers, not generator scope.  For this milestone, implement only enough survey behavior to make the first loop understandable.

## D3. The first objective route is visible and explicit

The player should not have to infer where to go from raw terrain.

After surveying, show or mark a route from the harbor to exactly one first objective. The first objective is:

```text
primary objective: ordinary cave or cave-like transition
secondary objective: inland site, if the cave objective is unavailable
```

The route can be a highlighted path, UI marker, simple line overlay, minimap marker, or message-driven “follow the old road east/north/etc.” prompt. The implementation may be visually simple, but the player must understand where to go.

The existing route artifact already supports selected debug routes, including starting-port routes when endpoints exist. Current examples include starting port to limestone gorge and starting port to lava-tube skylight. 

## D4. The clearable blockage does exactly one thing

The first blockage blocks or penalizes the road route until handled.

For the first playable loop, implement only one interaction:

```text
clear blockage
```

This action changes the relevant route segment from blocked/impaired to passable/repaired for the player.

Do not implement labor crews, tools, construction materials, time accounting, injury risk, skill checks, multi-stage repair, weather delays, AI workers, base assignments, or economic costs yet.

The current metadata already includes route segment state, blockage reference, endpoint references, and actor-profile cost hints, so the runtime action should mutate or overlay that existing state rather than inventing a new obstruction model. 

## D5. The first cave handoff may use a placeholder interior

The first playable loop requires entering a cave-like transition and landing somewhere playable.

It does not require final dungeon generation.

The first implementation may choose either:

```text
Option A: minimal generated one-room cave
Option B: placeholder cave room fixture
```

Decision: use **Option A** if an existing dungeon/GameMap conversion path can be used in a small PR. Use **Option B** if that integration starts expanding beyond one focused PR.

The transition must carry over and display at least some metadata from the overland transition: cave type, hydrology role, seasonal state, flow group, nearby affordances, handoff tags, or evidence tags.

The transition artifact already preserves cave type, hydrology role, seasonal state, flow group, substrate, elevation band, nearby affordances, handoff tags, and evidence tags for downstream dungeon generation. 

## D6. The first completion condition is “return to port with a discovery”

The loop completes when all of these are true:

```text
player entered the cave/interior
player acquired or recorded one discovery
player returned to the ruined harbor / starting port
```

This is more valuable than ending at the inland site because it proves two-way traversal, transition state, objective state, and loop closure.

The discovery can be minimal:

```text
discovery_id: first_cave_survey
label: "Surveyed the first cave mouth"
source: cave transition or cave room
```

No inventory item is required. No full journal system is required.

---

# Scavenge Inventory: Existing Pieces To Reuse

## Rule

Before adding new first-playable code, check whether an existing tool, test, debug viewer, or gameplay system already solves part of the problem.

The first-playable loop should consolidate existing pieces into one coherent path. It should not create a second world model, second renderer, second action system, second survey system, second repair system, or second map-loading pipeline.

## High-value pieces already in the repo

### 1. tools/play_game.py
* **Command**: `python tools/play_game.py --mode gui --seed 20260604`
* **Current value**: This is the closest existing thing to the desired first-playable launcher.
  It already supports:
  - `python tools/play_game.py --mode cli`
  - `python tools/play_game.py --mode gui`
  - `python tools/play_game.py --arrow generated_dungeon.arrow --mode cli`
  - `python tools/play_game.py --arrow generated_dungeon.arrow --mode gui`
  The file explicitly documents CLI and GUI startup for both generated overland starting port and Arrow/IPC shaped maps.
* **Scavenge decision**: Use `tools/play_game.py` as the base for first-playable launch behavior. Do not start with a brand-new launcher unless `tools/play_game.py` becomes actively obstructive.
* **Reuse these pieces**:
  - `create_gamestate_from_overland(seed, width, height)` already loads the starting overland game map and creates a `GameState` with player position, FOV, disabled sound, disabled AI, and deterministic seed wiring.
  - `run_gui_mode(...)` already handles PySide6/window-manager import, GUI fallback to CLI, config/keybinding loading, `MainLoop` construction, and `WindowManager` setup.
  - `run_cli_mode(...)` already provides a simple movement/debug walker using the same `MainLoop.handle_action(...)` path as GUI gameplay.
* **First-playable change**: Add one of these:
  `python tools/play_game.py --mode gui --seed 20260604 --first-playable`
  or:
  `python main.py --first-playable`
  *Decision*: First add `--first-playable` to `tools/play_game.py`, then later make `main.py --first-playable` forward to it if desired.
  *Reason*: `tools/play_game.py` already owns the exact GUI/CLI/seed/Arrow startup seam we need.

### 2. game/world/start_overland.py
* **Current value**: This is already the production-ish helper for generating the merged starting port and converting it into a runtime `GameMap`.
  It already:
  - Generates the overland region.
  - Builds the starting port from overland.
  - Generates the settlement.
  - Merges the settlement into overland.
  - Applies optional hydrology state.
  - Converts overland to `GameMap` with metadata.
  - Chooses a starting spawn.
  The documented merge path is already implemented:
  - `starting_port_from_overland(...)`
  - `generate_settlement(...)`
  - `merge_settlement_into_overland(...)`
  - `overland_to_game_map(..., with_metadata=True)`
* **Scavenge decision**: Use `load_starting_overland_game_map(...)` as the base for first-playable map creation. Do not duplicate starting-port generation in a new expedition module.
* **Reuse these pieces**: `choose_starting_overland_spawn(...)` already checks the metadata sidecar, looks for `starting_contract["player_spawn"]`, falls back to the harbor point, searches nearby human-walkable tiles, then falls back to the first human-walkable tile.
* **First-playable change**: Extend this file only if needed to expose a richer startup result:
  ```python
  @dataclass(slots=True)
  class StartingOverlandRuntime:
      game_map: GameMap
      player_spawn: tuple[int, int]
      selected_route_id: str | None
      selected_blockage_id: str | None
      selected_transition: tuple[int, int] | None
  ```
  But do not add that until the first-playable route/objective resolver actually needs it.

### 3. Existing survey system: game/systems/survey.py
* **Current value**: A survey system already exists.
  It already collects evidence coordinates from transitions, harbor, blockages, resource sites, waystation candidates, inland sites, cave refs, and route segment endpoints.
  It already implements `survey_coordinate(...)`, which reveals evidence tags from transitions, starting-contract features, cave refs, and route endpoints, stores them in `gs.discovered_evidence`, and emits discovery messages.
  It also already implements `check_automatic_survey(...)`, which surveys visible evidence coordinates.
* **Scavenge decision**: Do not create a new first-playable survey system from scratch. Use `game.systems.survey` as the base.
* **First-playable change**: Add a higher-level helper that surveys the starting region as a deliberate command:
  ```python
  def survey_starting_region(gs: GameState) -> FirstPlayableSurveyResult:
      ...
  ```
  This should call or reuse existing lower-level functions instead of replacing them.
  *Suggested result*:
  ```python
  @dataclass(slots=True)
  class FirstPlayableSurveyResult:
      harbor: tuple[int, int] | None
      water_sites: list[tuple[int, int]]
      resource_sites: list[tuple[int, int]]
      road_endpoints: list[tuple[int, int]]
      blockages: list[tuple[int, int]]
      cave_refs: list[tuple[int, int]]
      inland_sites: list[tuple[int, int]]
      selected_objective: tuple[int, int] | None
      selected_objective_kind: str
  ```
  *Action-handler integration already exists*: `engine/action_handler.py` already supports action type `"survey"`, defaults to player position when no target coordinate is supplied, calls `survey_coordinate(...)`, and consumes a turn. So the first-playable work should extend this action, not invent a separate command dispatcher.

### 4. Existing survey tests: tests/game/test_survey_system.py
* **Current value**: There are already tests for:
  - surveying transition evidence,
  - surveying route endpoint evidence,
  - surveying harbor evidence,
  - automatic survey of visible evidence,
  - action-handler integration for `"survey"`.
* **Scavenge decision**: Extend these tests or mirror their setup for first-playable integration tests. Do not write first-playable survey tests that ignore the existing survey/action-handler path.
* **First-playable test additions**: Add tests for:
  - `survey_starting_region` finds harbor, blockage, cave/inland objective
  - `survey_starting_region` sets first-playable objective state
  - survey action can drive first-playable survey when in first-playable mode

### 5. Existing repair/blockage system: game/systems/repair.py
* **Current value**: A blockage-clearing system already exists.
  `clear_blockage_at(gs, x, y)` already:
  - reads `game_map.overland_metadata`,
  - looks up `starting_contract["blockages"]`,
  - marks the blockage as cleared,
  - updates the associated route segment to `RouteSegmentState.REPAIRED`,
  - adds `EvidenceTag.RECENT_REPAIR`,
  - changes the tile to floor,
  - updates transparency,
  - updates material to road,
  - updates movement cost to 1.0,
  - updates traversal class to normal,
  - emits a success message,
  - triggers rediscovery through the survey system.
* **Scavenge decision**: Do not build a new obstruction system for first playable. Use `game.systems.repair.clear_blockage_at(...)`.
* **First-playable change**: Add a tiny resolver around existing metadata:
  ```python
  def find_first_playable_blockage(gs: GameState) -> tuple[int, int] | None:
      ...
  ```
  Then feed the coordinate into the existing action:
  `{"type": "repair", "x": x, "y": y}`
  *Action-handler integration already exists*: `engine/action_handler.py` already supports action type `"repair"`, defaults to player position when no target coordinate is supplied, calls `clear_blockage_at(...)`, and consumes a turn if the repair succeeds.

### 6. Existing repair tests: tests/game/test_repair_system.py
* **Current value**: The tests already verify that clearing a blockage:
  - changes a wall tile to floor,
  - restores walkability,
  - changes movement cost from infinity to 1.0,
  - changes material to road,
  - changes traversal class to normal,
  - changes route segment state from blocked to repaired,
  - adds recent-repair evidence,
  - emits a message,
  - is idempotent,
  - works through `process_player_action({"type": "repair", ...})`.
* **Scavenge decision**: Use this as the canonical behavior for the first-playable blockage. Do not weaken it. Do not bypass it.
* **First-playable test additions**: Add tests that use generated/default first-playable metadata rather than only the 5×5 mock fixture:
  - default first-playable seed contains a clearable blockage
  - first-playable blockage resolver returns a coordinate
  - repair action clears the default generated blockage
  - route segment state changes after repair

### 7. Existing seasonal/hydrology action support
* **Current value**: `engine/action_handler.py` already supports `"change_season"` actions, including a specific season name or cycling the season.
  `tests/game/test_seasons_system.py` already verifies seasonal state loading, seasonal walkability/cost changes, actor traversal differences, and action-handler integration.
* **Scavenge decision**: Do not include seasonal gameplay in the first-playable loop, but keep this as a debug/test tool.
* **Use for first playable**: Use seasons only for debugging blocked routes, testing wet/dry cave transition behavior, and manual QA of route viability. Do not make season changing required to complete the first loop.

### 8. settlegen.ui.server
* **Command**: `python -m settlegen.ui.server`
* **Current value**: This is a settlement-generation visual/debug server. It exposes a FastAPI app that generates settlements from request parameters and returns name, population, building count, district count, and ASCII map.
* **Scavenge decision**: Use this for visual inspection and tuning of starting-port settlement generation. Do not integrate this server into first-playable runtime.
* **Useful pieces**: The server demonstrates a compact request/response shape for settlement generation using `SettlementConfig` and `SettlementGenerator`.
* **First-playable use**: Use it to answer: Does the generated starting port look usable? Are roads/docks/buildings visually coherent? Does seed 20260604 produce a port we want? Do not make first-playable depend on FastAPI, browser UI, or server availability.

### 9. Lighting/FOV visual tool
* **Command**: `python -m tools.lighting_fov_tool.main`
* **Current value**: This is a GUI debugging/tuning tool for lighting, FOV, emitter visibility, compositing, cone/beam controls, ambient spill, and gameplay-view clipping.
* **Scavenge decision**: Use this tool for lighting/FOV inspection only. Do not copy its debug lighting backend into gameplay.
* **First-playable use**: Use it when first cave room is too dark, transition/interior visibility looks wrong, player FOV does not match expected cave visibility, or lighting leaks through cave blockers.
* **Required regression check**: Before treating a visual/FOV change as correct, run:
  `python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py`

### 10. play_debug.py and play_3d_debug.py
* **Commands**:
  - `python play_debug.py --seed 42`
  - `python play_3d_debug.py --arrow generated_dungeon.arrow`
* **Current value**: These are lightweight 2D and 3D dungeon debug viewers. The ADR says both can load an existing shaped `generated_dungeon.arrow` or invoke the shared orchestrator pipeline when no file is present. They must not own independent dungeon generation or connectivity repair.
* **Scavenge decision**: Use these for cave/dungeon inspection and spawn/camera ideas. Do not base first-playable runtime on them.
* **Reuse concepts, not whole viewer**: Scavenge Arrow loading expectations, spawn fallback ideas, camera/movement debug logic, and 3D visual inspection of generated dungeon artifacts. But keep generation in `Dungeon/` / `orchestrator.py`.

---

# Non-goals

Do not include these in first-playable work unless this document is updated:

1. Full continent-scale travel.
2. Full settlement simulation.
3. Full base management.
4. Complete expedition logistics.
5. Crew assignment systems.
6. Economy, supplies, wages, or trade.
7. Full archaeology/history inference.
8. Full map-knowledge/fog-of-war system.
9. Complete dungeon generator tuning.
10. Full spell system.
11. Full community NPC AI integration.
12. Combat balance pass.
13. Broad item/equipment migration.
14. Rendering dirty-rect optimization.
15. Additional LOS optimization beyond integration/regression safety.
16. Large UI redesign.
17. Procedural quest system.
18. Multiple endings.
19. Multiple biomes or alternate starts.
20. Save/load hardening, unless a tiny checkpoint is needed for the loop.

Performance work should remain profiling-driven. The current performance guidance says old combat/perception assumptions are stale and the next optimization should start with fresh `advance_turn()` or `process_turn()` profiling. 

---

# User-facing loop

## Player experience target

The player should experience this sequence:

1. The game opens on the ruined harbor / starting port.
2. The player can move around the visible settlement/harbor surface.
3. The UI tells the player they can survey the area.
4. The player uses the survey command.
5. The UI reveals or marks:

   * fresh water,
   * resource site,
   * ancient road,
   * clearable blockage,
   * cave mouth or cave-like transition,
   * inland objective.
6. The UI gives one explicit objective:

   * “Follow the ancient road to the first cave.”
7. The player follows a visible route.
8. The player encounters a blockage.
9. The player clears the blockage with one command.
10. The route becomes passable.
11. The player reaches the cave transition.
12. The player enters the cave.
13. The player survives or explores one room.
14. The player records one discovery.
15. The player returns to the harbor.
16. The game shows a loop-complete message.

## Required loop-complete message

Use a simple explicit completion message:

```text
Expedition complete: first cave surveyed and route back to port confirmed.
```

Do not hide this behind ambiguous UI state. The first playable loop needs an unambiguous success signal.

---

# Runtime concepts

## Expedition state

Add a small runtime state object. Keep it boring and explicit.

Suggested module:

```text
game/expedition/state.py
```

Suggested model:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExpeditionState:
    survey_completed: bool = False
    route_revealed: bool = False
    blockage_cleared: bool = False
    cave_entered: bool = False
    discovery_recorded: bool = False
    returned_to_port: bool = False
    loop_completed: bool = False
    active_objective_id: str | None = None
    discovery_ids: set[str] = field(default_factory=set)
```

Rules:

* This state is runtime gameplay state.
* It does not belong in worldgen.
* It does not require save/load in the first PR unless save/load already supports similar state cheaply.
* It should be deterministic from the generated world plus player actions.
* It should not mutate overland artifact files.

## Objective IDs

Use fixed IDs for first-playable objectives:

```text
survey_starting_region
follow_ancient_road
clear_first_blockage
enter_first_cave
record_first_discovery
return_to_port
```

Do not generate procedural objective IDs for this milestone.

## Discovery IDs

Use fixed IDs:

```text
first_cave_survey
first_route_reopened
```

Only `first_cave_survey` is required for loop completion.

`first_route_reopened` is optional flavor/state for later UI.

---

# Data contract usage

## Starting region contract

Use `overland_metadata.json` and the runtime metadata sidecar as the source of truth for starting-region references.

Required references:

```text
ruined harbor / starting port
local survey zone
ancient road
clearable blockage
ordinary cave or cave-like transition
inland site
route segments
```

The current metadata already includes a `starting_region_contract` entry referencing the ruined harbor, survey zone, resource sites, road, blockage, waystation, inland site, and ordinary cave. 

## Transition selection

Pick the first cave target with this priority:

1. Ordinary cave.
2. Karst hydrology transition.
3. Lava-tube transition.
4. Inland site transition.
5. Any valid transition in the starting region.

For cave-like transitions, prefer records with richer handoff/evidence metadata.

## Route selection

Pick the first route with this priority:

1. Starting port to selected cave transition.
2. Starting port to inland site.
3. Starting port to limestone gorge.
4. Starting port to lava-tube skylight.
5. Generated route from starting port to selected transition using actor traversal profile `HUMAN_ON_FOOT`.

The current actor traversal profile system already defines `HUMAN_ON_FOOT` and helpers for actor-specific movement cost grids. 

## Blockage selection

Pick the blockage referenced by the starting-region contract.

If multiple blockages exist, choose the first blockage on the selected route.

If no blockage exists, create a runtime-only “fallen stones” blockage on the route for development builds, but mark this as a fallback and add a test that the generated contract should normally provide the blockage.

---

# Implementation phases

## Phase 0: Add this plan to the repo

Add this file:

```text
docs/First Playable Expedition Loop.md
```

Update `docs/Current Status.md` with a new row or note:

```text
First playable expedition loop | game/expedition/, overland runtime UI, transition handling | Planned / in progress | python main.py or relevant overland UI command | Binds starting port, survey, route, blockage, cave transition, and return condition into one playable loop | Track against docs/First Playable Expedition Loop.md
```

Acceptance criteria:

* This document exists.
* `docs/Current Status.md` points to it.
* LLM agents can identify this as the current vertical-slice plan.

## Phase 1: Create first-playable launch path

Add a deterministic launch path that always loads or generates the merged starting port and starts the player there.

Suggested command shape:

```bash
python main.py --first-playable
```

or, if main argument handling is not ready:

```bash
python tools/play_first_expedition.py
```

Decision: prefer `python main.py --first-playable` if it does not disrupt the normal entrypoint. Otherwise add `tools/play_first_expedition.py`.

Required behavior:

* Generate or load overland with starting port merged.
* Convert it to the runtime `GameMap`.
* Attach overland metadata sidecar.
* Spawn player at ruined harbor/dock.
* Open the visual UI directly.

Acceptance criteria:

* One command starts the first playable loop.
* Player appears at the starting port.
* Map metadata is available at runtime.
* The seed is fixed by default.
* A custom seed may be accepted later, but is not required.

Suggested default seed:

```text
20260604
```

This seed already appears in the documented overland generation examples. 

## Phase 2: Spawn and start-state validation

Add a resolver that finds the player spawn point.

Suggested module:

```text
game/expedition/start.py
```

Responsibilities:

* Locate ruined harbor / starting port feature.
* Prefer dock/harbor walkable tile.
* Fall back to nearest road tile inside the port.
* Fall back to nearest walkable tile in the survey zone.
* Fail loudly if no valid spawn exists.

Suggested function:

```python
def resolve_starting_port_spawn(game_map: GameMap) -> tuple[int, int]:
    ...
```

Acceptance criteria:

* Spawn is deterministic.
* Spawn is walkable.
* Spawn is inside or adjacent to the starting port/harbor.
* Spawn is not inside a wall, blocked water tile, or transition tile unless transitions are explicitly walkable.
* Test covers normal spawn and fallback spawn.

## Phase 3: Survey command

Add one command:

```text
Survey Area
```

Suggested key:

```text
v
```

Reason: “v” can stand for “survey/view,” and it avoids occupying common movement/action keys. If this conflicts with existing keybindings, choose the nearest unused key and document it.

Survey behavior:

* Reads local overland metadata.
* Finds starting-region references.
* Reveals or marks:

  * fresh water,
  * resource site,
  * ancient road,
  * clearable blockage,
  * cave transition,
  * inland objective.
* Sets:

```python
expedition_state.survey_completed = True
expedition_state.route_revealed = True
expedition_state.active_objective_id = "follow_ancient_road"
```

UI output:

```text
Survey complete: harbor, road, water, blockage, and first cave marked.
```

If cave is unavailable:

```text
Survey complete: harbor, road, water, blockage, and inland site marked.
```

Non-goals:

* No persistent map annotations editor.
* No journal prose system.
* No procedural discovery text.
* No hidden skill checks.

Acceptance criteria:

* Survey command works from the starting port.
* Survey command is idempotent.
* Survey command does not mutate worldgen artifacts.
* Survey result is visible in the UI.
* Survey identifies at least one valid objective.

## Phase 4: Route highlight / route-following objective

After survey, expose a visible route.

Minimum viable implementation:

* Highlight route tiles in the UI, or
* Mark next route tile/objective marker, or
* Show route as a simple overlay/minimap path, or
* Display clear text direction plus objective marker.

Decision: implement route tile highlighting if the UI already supports overlays. Otherwise implement objective marker plus text.

Route state:

```python
active_objective_id = "follow_ancient_road"
```

Required objective text:

```text
Objective: follow the ancient road to the first cave.
```

Fallback text:

```text
Objective: follow the ancient road to the inland site.
```

Acceptance criteria:

* After survey, player can tell where to go.
* Route uses overland route metadata when available.
* If metadata route is unavailable, runtime pathfinding may compute a route from port to target using `HUMAN_ON_FOOT`.
* Route does not require all-pairs route generation.
* Test proves a route exists for the default first-playable seed.

## Phase 5: Clearable blockage interaction

Add one interaction when the player is adjacent to or standing on the blockage tile:

```text
Clear Blockage
```

Suggested key:

```text
c
```

If `c` conflicts, use the existing interact key and make blockage clearing a context action.

Behavior:

* Before clearing, the blockage blocks or heavily penalizes route traversal.
* Player uses the action.
* State updates:

```python
expedition_state.blockage_cleared = True
```

* Route segment state updates in runtime metadata or an expedition overlay:

```text
BLOCKED -> REPAIRED
```

or:

```text
BLOCKED -> CLEAR
```

Decision: use `REPAIRED` if that is already the active route-segment vocabulary. Otherwise use `CLEAR`.

The overland roadmap notes that runtime metadata already drives actor traversal with state-based costs and that repaired/blocked route segment semantics exist. 

Required message:

```text
You clear enough of the blockage to reopen the road.
```

Non-goals:

* No repair animation.
* No resource cost.
* No time cost beyond one action/turn.
* No tool requirement.
* No multi-actor job.
* No construction menu.

Acceptance criteria:

* Blockage can be found from starting-region metadata.
* Player can clear it.
* Route becomes passable or lower cost after clearing.
* State change is visible to the player.
* Test proves blockage state changes.

## Phase 6: Cave transition and minimal interior

Add transition handling from overland to one minimal cave/interior map.

Transition trigger:

* Player stands on cave transition tile and presses interact/enter, or
* Player moves onto transition tile and confirms entry if confirmation already exists.

Decision: prefer explicit interact/enter. Avoid accidental transition on movement for first playable.

Required message before entry:

```text
Enter the cave? [Enter]
```

Required transition metadata display:

At entry or inside the cave, show at least two of:

```text
cave_type
hydro_role
seasonal_state
flow_group
nearby_affordances
handoff_tags
evidence_tags
```

Example:

```text
Cave entered: karst window, dry-season flow group 3.
```

Interior requirements:

* At least one room.
* Player can move.
* Room has exit back to overland.
* Room has one discovery trigger.
* Room does not need enemies.
* Room does not need loot.
* Room does not need final cave lighting.

Decision: no required combat in first playable cave. Survival means entering, moving, recording discovery, and returning.

Suggested discovery trigger:

* Inspect cave wall.
* Step onto marked survey point.
* Use survey inside cave.
* Interact with evidence marker.

Pick the simplest implementation.

Acceptance criteria:

* Player can enter cave.
* Player appears in valid interior spawn.
* Player can move inside.
* Player can record `first_cave_survey`.
* Player can exit back to the same overland transition.
* Test proves transition round-trip works.

## Phase 7: Discovery recording

Add minimal discovery recording.

State update:

```python
expedition_state.discovery_ids.add("first_cave_survey")
expedition_state.discovery_recorded = True
```

Required message:

```text
Discovery recorded: first cave surveyed.
```

Non-goals:

* No inventory item required.
* No journal UI required.
* No procedural prose required.
* No XP or skill reward required.
* No codex required.

Acceptance criteria:

* Discovery can be recorded exactly once.
* Recording is idempotent.
* State persists at least during the current runtime session.
* UI shows a clear message.

## Phase 8: Return to port and complete loop

When the player returns to the starting port after recording `first_cave_survey`, complete the loop.

Completion condition:

```python
if (
    expedition_state.cave_entered
    and expedition_state.discovery_recorded
    and player_is_at_starting_port
):
    expedition_state.returned_to_port = True
    expedition_state.loop_completed = True
```

Required message:

```text
Expedition complete: first cave surveyed and route back to port confirmed.
```

Optional next message:

```text
First playable loop complete.
```

Acceptance criteria:

* Returning before cave discovery does not complete the loop.
* Returning after cave discovery completes the loop.
* Completion fires once.
* Completion state is visible.
* Test proves completion condition.

---

# Testing plan

The repo already documents required local checks: Black, Ruff, strict mypy, deterministic-randomness checker, unit tests, compileall, and LLM policy sync.  Use those checks for completed PRs, but first-playable work also needs focused end-to-end tests.

## Required tests

Add or extend tests under:

```text
tests/test_first_playable_expedition.py
```

or, if existing overland integration tests are the better home:

```text
tests/test_overland_integration.py
```

The current overland integration tests already cover stable seeded generation, transition artifacts, route artifacts, starting-region metadata, cave transition payloads, headless generation, merged starting-port generation, actor-specific inspection, and `GameMap` conversion.  Build on that instead of duplicating lower-level generator tests.

### Test 1: first playable bundle exists

Given the default first-playable seed:

* overland bundle generates,
* starting port merge succeeds,
* metadata sidecar exists,
* starting-region contract exists,
* ruined harbor exists,
* road exists,
* blockage exists,
* cave or fallback inland objective exists.

### Test 2: spawn is valid

* Resolve spawn.
* Assert tile is in bounds.
* Assert tile is walkable.
* Assert tile is near starting port/harbor.

### Test 3: survey resolves objective

* Create runtime state.
* Run survey resolver.
* Assert survey completed.
* Assert active objective is set.
* Assert at least one route/objective marker exists.

### Test 4: route exists

* Resolve route from starting port to selected objective.
* Prefer artifact route.
* Fall back to runtime path.
* Assert route length > 1.
* Assert route starts near port.
* Assert route ends near cave/inland target.

### Test 5: blockage clears

* Resolve blockage.
* Assert initial state is blocked/impaired.
* Clear blockage.
* Assert state is repaired/clear.
* Assert expedition state updated.

### Test 6: cave transition round-trip

* Resolve cave transition.
* Enter cave.
* Assert interior map exists.
* Assert player spawn is valid.
* Exit cave.
* Assert player returns to overland near same transition.

### Test 7: discovery and completion

* Enter cave.
* Record discovery.
* Return to port.
* Assert loop completed.
* Assert completion message/event emitted once.

## Manual smoke test

Add a checklist to the PR description:

```text
- [ ] Start first-playable mode.
- [ ] Confirm player spawns at ruined harbor / starting port.
- [ ] Use survey command.
- [ ] Confirm route/objective appears.
- [ ] Follow road.
- [ ] Clear blockage.
- [ ] Enter cave.
- [ ] Record discovery.
- [ ] Exit cave.
- [ ] Return to port.
- [ ] Confirm loop-complete message appears.
```

## Performance checks

Do not optimize first. If the first-playable loop feels slow, run the existing turn-processing benchmark before changing hot paths.

Relevant documented benchmark commands include:

```bash
python bench/bench_advance_turn.py --entities 50 --width 50 --height 50 --turns 1 --warmup-turns 0
python bench/bench_advance_turn.py --entities 100 --width 60 --height 60 --turns 1 --warmup-turns 0
```

The performance document says current follow-up work should profile the next dominant turn-processing bottleneck instead of re-implementing stale recommendations. 

---

# Suggested file/module ownership

## New files

```text
docs/First Playable Expedition Loop.md
game/expedition/__init__.py
game/expedition/state.py
game/expedition/start.py
game/expedition/survey.py
game/expedition/objectives.py
game/expedition/blockage.py
game/expedition/transitions.py
tests/test_first_playable_expedition.py
```

## Existing files likely touched

Exact file names may differ, but likely touch points are:

```text
main.py
orchestrator.py
config/keybindings.toml
tools/generate_overland.py
tools/play_from_arrow.py
worldgen/overland/
game/world/
game/game_state.py
engine/
```

## Keep boundaries clear

Worldgen owns:

```text
terrain artifacts
features
routes
transitions
metadata sidecar
starting-region contract
```

Runtime gameplay owns:

```text
survey command
objective state
discovery state
blockage-cleared overlay/state
transition execution
loop completion
UI messages
```

Do not push runtime expedition state back into worldgen artifacts.

---

# LLM agent instructions

When an LLM agent works on this project, it must follow these rules for first-playable work.

## Stay on the vertical slice

The task is to make this loop playable:

```text
start at port
survey
follow road
clear blockage
enter cave
record discovery
return to port
complete loop
```

Do not expand sideways into full systems.

## Prefer existing contracts

Use existing overland artifacts and metadata:

```text
overland_tiles.arrow
overland_hydrology.arrow
overland_features.arrow
overland_affordances.arrow
overland_transitions.arrow
overland_routes.arrow
overland_metadata.json
```

The current overland docs identify these as authoritative artifacts. 

## Do not invent a second world model

The overland terrain contract already exists. Runtime code should consume it.

Do not create a parallel “tutorial world schema,” “quest world schema,” or “special first map format.”

## Keep survey small

Survey reveals known metadata. It is not:

```text
fog of war
journal
rumor system
knowledge graph
archaeology model
map editor
quest generator
```

## Keep blockage small

Blockage clearing is one action. It is not:

```text
construction
labor
economy
tooling
crew management
multi-turn repair
simulation job
```

## Keep cave small

The first cave is one playable interior. It is not final dungeon generation.

Accept placeholder/minimal cave if full dungeon handoff becomes too large.

## Keep completion explicit

The loop must emit a clear completion message. Do not rely on implicit state.

## Do not optimize without profiling

The LOS ASM work is good, but the first-playable milestone is about gameplay integration. Any further hot-path work must be justified with current profiling.

## Add tests with each gameplay binding

Do not add only UI behavior. Every resolver or state transition should have a small test.

---

# Milestone breakdown

## Milestone A: Document and launch path

Deliverables:

* Add this document.
* Add first-playable launch mode.
* Generate/load merged starting port.
* Spawn player at ruined harbor.

Exit criteria:

```text
One command opens the overland UI with the player at the starting port.
```

## Milestone B: Survey and route

Deliverables:

* Add expedition state.
* Add survey command.
* Resolve objective.
* Reveal route or marker.

Exit criteria:

```text
Player can survey and understand where to go.
```

## Milestone C: Blockage

Deliverables:

* Resolve blockage from metadata.
* Add clear action.
* Update runtime route state/cost.
* Show message.

Exit criteria:

```text
Player can reopen the road.
```

## Milestone D: Cave transition

Deliverables:

* Resolve cave transition.
* Enter minimal cave/interior.
* Exit back to overland.
* Display handoff metadata.

Exit criteria:

```text
Player can make a round trip between overland and cave.
```

## Milestone E: Discovery and completion

Deliverables:

* Record first cave discovery.
* Detect return to port.
* Complete loop.
* Add end-to-end test.

Exit criteria:

```text
Player can finish the first playable expedition loop.
```

---

# Definition of done

First-playable work is done when all of these are true:

1. `python main.py --first-playable` or equivalent starts the loop.
2. Player spawns at the ruined harbor / starting port.
3. Survey command reveals the first route/objective set.
4. Route to cave or inland objective is visible.
5. Clearable blockage is present.
6. Player can clear the blockage.
7. Player can enter a cave/interior.
8. Cave/interior has one discovery.
9. Player can return to overland.
10. Player can return to port.
11. Loop-complete message appears.
12. Focused tests cover spawn, survey, route, blockage, transition, discovery, and completion.
13. Existing relevant overland integration tests still pass.
14. No broad new simulation systems were introduced.
15. Documentation points future contributors and LLMs to this plan.

---

# Revised implementation plan: scavenge-first

## PR 1: Document scavenge inventory and bless tools/play_game.py
* **Scope**:
  - `docs/First Playable Expedition Loop.md`
  - `docs/Current Status.md`
  - `tools/play_game.py`
* **Changes**:
  - Add this scavenge inventory.
  - Add `--first-playable` to `tools/play_game.py`.
  - Make `--first-playable` imply:
    - overland starting port,
    - default seed `20260604`,
    - GUI mode unless `--mode cli` is explicitly supplied,
    - no Arrow input unless explicitly supplied for debug.
  - Add startup message:
    `First playable expedition mode: starting at ruined harbor.`
  - Do not add new gameplay systems in this PR.

## PR 2: First-playable state as thin orchestration
* **Scope**:
  - `game/expedition/state.py`
  - `game/expedition/resolvers.py`
  - `tests/test_first_playable_expedition.py`
* **Changes**:
  - Add only state and resolvers.
  - Do not duplicate existing survey or repair logic.
  - Suggested state:
    ```python
    @dataclass(slots=True)
    class ExpeditionState:
        survey_completed: bool = False
        route_revealed: bool = False
        blockage_cleared: bool = False
        cave_entered: bool = False
        discovery_recorded: bool = False
        returned_to_port: bool = False
        loop_completed: bool = False
        active_objective_id: str | None = None
        discovery_ids: set[str] = field(default_factory=set)
    ```
  - Suggested resolvers:
    - `resolve_starting_contract(gs: GameState) -> Mapping[str, object]: ...`
    - `resolve_first_playable_blockage(gs: GameState) -> tuple[int, int] | None: ...`
    - `resolve_first_playable_cave_or_inland_target(gs: GameState) -> tuple[int, int] | None: ...`
    - `resolve_first_playable_route(gs: GameState) -> list[tuple[int, int]]: ...`
    - `is_player_at_starting_port(gs: GameState) -> bool: ...`
  - These functions should read `game_map.overland_metadata`. They should not generate new terrain.

## PR 3: Survey command uses existing survey system
* **Scope**:
  - `game/systems/survey.py`
  - `engine/action_handler.py`
  - `tools/play_game.py` or UI input layer
  - `tests/game/test_survey_system.py`
  - `tests/test_first_playable_expedition.py`
* **Changes**:
  - Add `survey_starting_region(gs)`. It should reuse `get_all_evidence_coords(...)` and `survey_coordinate(...)`.
  - It should set first-playable expedition state if present.
  - It should emit:
    `Survey complete: harbor, road, water, blockage, and first cave marked.`
  - Wire a key or CLI command to action type `"survey"`.
  - *Decision*: keep action type `"survey"`; do not add `"expedition_survey"`.

## PR 4: Blockage action uses existing repair system
* **Scope**:
  - `game/systems/repair.py`
  - `game/expedition/resolvers.py`
  - UI/CLI input layer
  - `tests/game/test_repair_system.py`
  - `tests/test_first_playable_expedition.py`
* **Changes**:
  - Use `resolve_first_playable_blockage(gs)` to identify the blockage.
  - Use existing action type `"repair"`.
  - Use existing `clear_blockage_at(gs, x, y)`.
  - Set expedition state after successful repair.
  - Keep existing behavior that marks route segment repaired and adds recent-repair evidence.
  - *Decision*: do not introduce a new `"clear_blockage"` action type. Existing `"repair"` is sufficient.

## PR 5: Cave transition handoff
* **Scope**:
  - `game/expedition/transitions.py`
  - `game/world/` or `game/systems/`
  - `tests/test_first_playable_expedition.py`
* **Changes**:
  - Resolve transition from `game_map.overland_metadata.transitions` and/or `starting_contract["cave_refs"]`.
  - Add action type `"enter_transition"` or `"enter"`.
  - Create minimal one-room cave if real dungeon handoff is too large.
  - Preserve and display at least two metadata fields: cave type, hydrology role, seasonal state, flow group, handoff tags, evidence tags.
  - *Decision*: `play_debug.py` and `play_3d_debug.py` remain inspection tools. Do not route first-playable runtime through them.

## PR 6: Discovery and completion
* **Scope**:
  - `game/expedition/state.py`
  - `game/expedition/completion.py`
  - `tests/test_first_playable_expedition.py`
* **Changes**:
  - Record `first_cave_survey`.
  - Detect return to starting port.
  - Emit:
    `Expedition complete: first cave surveyed and route back to port confirmed.`
  - Add end-to-end test.

---

# Explicit “do not start from scratch” list

Do not replace these:
* `tools/play_game.py`                    -> use as launcher base
* `game/world/start_overland.py`          -> use as starting-port map builder
* `game/systems/survey.py`                -> use as survey/evidence base
* `game/systems/repair.py`                -> use as blockage-clearing base
* `engine/action_handler.py`              -> use existing action dispatch
* `tests/game/test_survey_system.py`      -> extend for survey behavior
* `tests/game/test_repair_system.py`      -> extend for blockage behavior
* `tests/game/test_seasons_system.py`     -> use for seasonal debug confidence
* `tools/lighting_fov_tool/`              -> use for visual/FOV debugging only
* `settlegen/settlegen/ui/server.py`      -> use for settlement visual inspection only
* `play_debug.py` / `play_3d_debug.py`      -> use for dungeon inspection only

---

# Immediate practical next command sequence

Run these manually while developing the first-playable branch:
* `python tools/play_game.py --mode gui --seed 20260604`
* `python tools/play_game.py --mode cli --seed 20260604`
* `python -m settlegen.ui.server`
* `python -m tools.lighting_fov_tool.main`
* `python play_debug.py --seed 42`
* `python play_3d_debug.py --arrow generated_dungeon.arrow`
* `python -m pytest tests/game/test_survey_system.py tests/game/test_repair_system.py tests/game/test_seasons_system.py`

*Interpretation*:
* `tools/play_game.py` tells us whether the starting-port gameplay path already opens.
* `settlegen.ui.server` tells us whether the port/town generation looks usable.
* `lighting_fov_tool` helps debug cave/interior visibility.
* `play_debug.py` and `play_3d_debug.py` help inspect dungeon artifacts, not runtime gameplay.
* survey/repair/season tests protect the already-existing systems we should extend.

The decisive takeaway: first-playable should be an orchestration and UI-binding layer over systems that already exist. The repo already has survey, repair, starting-overland generation, GUI/CLI play launch, settlement inspection, lighting/FOV inspection, and dungeon debug viewers. The missing piece is a single vertical-slice controller that wires them together and marks completion.

---

# Final implementation bias

Prefer simple, explicit, deterministic code.

Prefer fixed IDs over procedural abstractions.

Prefer one route, one blockage, one cave, one discovery, one completion condition.

Prefer runtime overlays over mutating generated artifacts.

Prefer tests over clever UI.

Prefer getting the loop playable over making any one subsystem final.

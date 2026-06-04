# Proposed Software Systems for Lost Continent Expedition Roguelike

## Version 2: Integrated Proposal Set

This document updates and expands the earlier `Proposed Software Systems.md` draft. It incorporates the current Simple RL repository architecture, the Lost Continent Expedition vision, and the pinned future-system ideas that are not yet implemented but now belong in the design backlog.

The systems below are **proposed architecture**, not claims that these modules already exist. Each proposal states how it should wire into current repository ownership boundaries.

Current repository anchors:

- `game/` owns production game state, systems, entities, AI integration, effects, items, and world logic.
- `engine/` owns rendering, lighting, FOV-facing presentation, and window management.
- `Dungeon/` owns procedural cave generation.
- `worldgen/` owns macro/world generation and should become the owner for overland topology work.
- `pathfinding/perception_systems.py` owns pathfinding-oriented sound and scent flow concepts.
- `game/world/` owns production FOV, LOS, visibility, memory, and map state.
- `game/ai/` owns production gameplay AI. `auto/` remains a GOAP tuning/simulation harness, not the production game loop.
- `ai/` remains R&D for community/social AI until specific features are promoted into production modules.
- `utils.game_rng.GameRNG` is the canonical randomness API for game logic.
- `magic/` and `game/effects/` are the natural owners for spell execution, magical work, and effect application.
- `game/skills/` owns game-facing skill integration. Top-level `skills/` owns reusable rules and research helpers.

---

# 1. Architectural Goal

The new systems should convert the existing simulation-heavy roguelike engine into the specific game described by the Lost Continent Expedition vision:

> Lead a small expedition, rebuild a foothold, follow ancient roads, survey ruins and caves, deposit knowledge at the Central Archive, manage social and logistical consequences, and uncover that the western continent is the epicenter of a magical phase transition from rigid order into wildness.

The software design should therefore prioritize:

1. **Walkable consequence** — base, roads, Waystations, caves, and field discoveries exist in physical map space.
2. **Knowledge as loot** — the highest-value reward is information that changes future options.
3. **Leadership opportunity cost** — every assignment removes a person, tool, or time block from another job.
4. **Socially consequential roster** — the Couples Draft and SocialBond system make deaths and absences materially affect settlement function.
5. **Legible simulation** — scent, roads, morale, research, and magic should expose enough clues for the player to reason.
6. **Deterministic implementation** — all stochastic behavior must use `GameRNG`.
7. **Graceful fallback** — every ambitious system must have a simpler deterministic version that preserves gameplay.

---

# 2. System Dependency Overview

The proposed systems should wire together like this:

```text
worldgen/
  ├─ overland topology, Ancient Roads, POIs, Doom Engine coordinate
  └─ emits macro map + route graph + region metadata
        ↓
Dungeon/
  └─ cave systems, shaped maps, depth/height/chamber data
        ↓
game/world/
  ├─ GameMap, region/chunk state, FOV, LOS, memory, terrain layers
  └─ receives worldgen/Dungeon outputs
        ↓
game/entities/
  ├─ EntityRegistry
  ├─ expedition members
  ├─ SocialBond / MentalState / KnowledgeFragment / Infrastructure components
  └─ BaseCamp entity and Waystation entities
        ↓
game/systems/
  ├─ infrastructure_system.py
  ├─ research_system.py
  ├─ morale_system.py
  ├─ expedition_assignment_system.py
  ├─ cave_survey_system.py
  ├─ overland_threat_system.py
  ├─ wildness_gradient.py
  ├─ ghost_term_system.py
  └─ existing combat, movement, death, sound, AI, equipment systems
        ↓
game/ai/
  ├─ GOAP adapter
  ├─ scheduler-facing actor policy
  ├─ sparse perception facts
  ├─ morale / assignment action selection
  ├─ production behavior selection
  ├─ perception snapshots
  └─ future morale-aware labor/planning hooks
        ↓
pathfinding/
  └─ scent/noise flow fields and flow-following helpers
        ↓
magic/ + game/effects/
  ├─ magical tool execution
  ├─ cultural interface tolerance checks
  ├─ Ghost Term generation
  └─ effect application
        ↓
engine/
  ├─ render base
  ├─ render entities
  ├─ render lighting
  ├─ viewport visual composition
  ├─ render overlays for roads, scents, survey, memory, research, morale, travel, and survey confidence
  └─ UI affordances via window/action handling

game/runtime/ + engine composition/
  ├─ energy scheduler owns authoritative simulation time
  ├─ `EventBatch` and `TurnResult` describe mutations
  ├─ dirty arrays / dirty rects drive derived updates
  └─ renderer consumes draw-ready viewport arrays rather than gameplay state directly
```

---

# 3. Cross-Cutting Implementation Rules

These apply to every new system.

## 3.1 Determinism

All randomness must use `utils.game_rng.GameRNG`.

Examples:

- Roster generation.
- Couple pairing.
- Road graph perturbation.
- Wildlife spawning.
- Scent-threshold checks.
- Research discovery ordering.
- Magical failure modes.
- Night events.
- Social stress response variation.

Do not use Python `random`, NumPy RNGs, UUID randomness, or OS randomness inside game logic.

## 3.2 Data Layout

Prefer explicit, data-oriented state.

Recommended:

- Polars DataFrames for large tables and batch state.
- NumPy arrays for dense numeric fields.
- Numba kernels for hot propagation/simulation loops.
- Small dataclasses or component records for entity-attached state.
- Immutable configuration loaded from YAML/TOML/JSON where appropriate.

Avoid broad object hierarchies unless they remove real duplication.

Do not introduce a Python object per map cell.

Prefer dense planes, typed compact batches, small dataclasses at module boundaries,
array kernels, version counters, dirty masks, dirty rects, and sparse tables for
events, animations, perception facts, and long-lived records.

## 3.3 Save/Load

Every proposed system needs serializable state:

- Component state in EntityRegistry.
- Dense arrays as compact binary/Arrow/NumPy-compatible payloads.
- Regional summaries as Polars tables.
- RNG state.
- Event queues.
- Active project state.
- Research progress.
- Road/Waystation condition.
- Social state.

## 3.4 Player-Facing Legibility

Every system should expose clues through:

- Map visuals.
- Base behavior.
- Companion reports.
- Tooltips or inspection text.
- Logs.
- Archive summaries.
- Environmental traces.
- UI overlays only where useful.

Opaque simulation is not a goal.

## 3.5 Turn-Authoritative Runtime

Simulation time should be owned by an authoritative energy scheduler.

The player taking a manual keypress, a hunter following a scent trail, a torch
burning down, a poison cloud spreading, a door closing after delay, a field party
traveling, a base worker completing labor, and a fast-forwarded rest all advance
through the same simulation path:

```text
input / runtime policy
-> scheduler step
-> action resolution
-> authoritative state mutation
-> `EventBatch`
-> dirty arrays / dirty rects
-> FOV / lighting / perception / memory updates
-> viewport composition
-> platform drawing
```

Realtime presentation must not become a second rules engine.

The invariant:

- Realtime mode calls the same scheduler more often.
- It does not introduce per-frame gameplay rules.

Runtime modes are policies over scheduler stepping, not separate game modes:

- MANUAL
- AUTO_WAIT
- TRAVEL
- REST
- FAST_FORWARD
- PAUSED
- ANIMATION_ONLY

When the player schedulable reaches the front of the queue:

- MANUAL -> pause and request input
- AUTO_WAIT -> inject WaitAction
- REST -> inject WaitAction until rest target or interruption
- TRAVEL -> inject next path movement until blocked or interrupted
- FAST_FORWARD -> run correct scheduler steps with sparse rendering
- PAUSED -> do not advance simulation
- ANIMATION_ONLY -> advance only presentation state

This enables deliberate turn play and fast simulation without duplicating combat,
AI, visibility, movement, lighting, status, or environmental rules.

## 3.6 Event Batches, Turn Results, and Dirty State

Every authoritative action should emit structured event data and dirty metadata.
Avoid a long stream of Python event objects in hot paths.

Use a compact event spine:

```text
EventBatch:
    event_type: uint16[n]
    actor_id: int32[n]
    target_id: int32[n]
    x0, y0, x1, y1: int16[n]
    importance: uint8[n]
    visibility: uint8[n]
    animation_hint: uint16[n]
    sound_hint: uint16[n]
    message_id: uint16[n]
    payload_offset: int32[n]
    payload_len: int16[n]
```

Use typed side tables, event-specific arrays, or a compact payload slab for
variable payloads. Do not use generic dictionaries for high-volume event payloads.

The result of resolving one scheduled action should be representable as:

```text
TurnResult:
    current_tick
    acting_sched_actor_id
    acting_entity_id
    action_type
    consumed_delay
    changed_entity_ids
    changed_xy
    changed_rects
    dirty_light_ids
    dirty_reason_mask
    events
```

Events feed:

- message log
- sound playback
- AI perception facts
- runtime interruption policy
- animation
- dirty rendering
- debug replay
- save replay
- tests

Dirty state should be array-oriented:

- changed_xy: int16[n, 2]
- changed_rects: int16[m, 4]
- dirty_reason_mask: uint32[h, w]
- dirty_light_ids: int32[k]
- dirty_entity_ids: int32[e]
- dirty_observer_ids: int32[o]
- scene_geometry_version: int64

Avoid Python set[Vec2] or renderer-side gameplay queries in hot paths.

---

# 4. Proposed System: Expedition Roster and Couples Draft

## Purpose

Generate the twenty-four-person expedition as a small, memorable, socially connected roster. The player drafts couples or family units rather than isolated workers, creating immediate strategic and emotional opportunity costs.

## Source of Truth

- `game/entities/registry.py` owns generated Actor entities.
- New game setup owns roster generation and player selection.
- `utils.game_rng.GameRNG` owns all procedural generation.

## Proposed Modules

- `game/expedition/roster_generation.py`
- `game/expedition/couples_draft.py`
- `game/entities/components.py` additions
- Optional data files under `data/expedition/`

## Proposed Components

```python
ExpeditionMember(
    role_primary: str,
    role_secondary: str,
    sex: str,
    age_band: str,
    temperament: str,
    fear_tag: str,
    ambition_tag: str,
    joined_reason: str,
    practical_limitation: str,
)

SocialBond(
    target_entity_id: int,
    bond_type: str,  # spouse, sibling, friend, mentor, rival
    strength: float,
)

LaborProfile(
    base_skills: dict[str, float],
    field_skills: dict[str, float],
    fatigue: float,
    availability: str,
)
```

## Data Flow

1. New game setup creates a pool of couples/family units.
2. The player drafts units until the roster reaches 24.
3. The generator creates Actor entities in `EntityRegistry`.
4. Each pair receives reciprocal `SocialBond` components.
5. Each entity receives skill, labor, morale, and identity traits.
6. `expedition_assignment_system.py`, `morale_system.py`, `research_system.py`, and field-party selection consume this data.

## Existing System Integration

- `game/entities/registry.py`: creates and queries roster members.
- `game/ai/`: reads assignment and morale states for behavior.
- `game/systems/ai_system.py`: schedules NPC/base labor behavior.
- `game/skills/`: optional bridge if role skills become game-facing skills.
- `utils.game_rng.GameRNG`: deterministic roster generation.

## Minimum Viable Version

- Draft 12 couples.
- Each member has name, role, base skill, field skill, and spouse bond.
- Assignments consume availability.
- Death of spouse applies morale penalty.

## Later Expansion

- Family groups beyond couples.
- Rivalries and ideological factions.
- Hidden fears or ambitions.
- Procedural dialogue hooks.
- Companion-specific interpretation of discoveries.

---

# 5. Proposed System: Expedition Assignment and Daily Work

## Purpose

Convert leadership into the core daily gameplay loop: the player assigns people and tools to base projects, road work, scouting, research, guarding, and field parties.

## Source of Truth

- `game/game_state.py` owns current day/turn and assignment state.
- `game/entities/registry.py` owns member availability.
- `game/systems/ai_system.py` and production AI execute autonomous work.

## Proposed Modules

- `game/systems/expedition_assignment_system.py`
- `game/expedition/assignments.py`
- `game/ui/assignment_panel.py` or equivalent UI layer
- `data/expedition/assignments.yaml`

## Proposed Components

```python
Assignment(
    assignment_type: str,
    target_entity_id: int | None,
    target_location_id: int | None,
    priority: int,
    started_turn: int,
)

Availability(
    state: str,  # available, field_party, injured, grieving, resting, assigned
    until_turn: int | None,
)

ProjectProgress(
    project_id: str,
    work_required: float,
    work_completed: float,
    required_roles: tuple[str, ...],
)
```

## Data Flow

1. Morning Council UI presents current resource, morale, project, road, and research state.
2. Player assigns members to work streams.
3. System validates required roles, tools, travel access, and morale constraints.
4. Assignments are stored on entities or project records.
5. Daily tick applies labor progress, fatigue, resource consumption, and risks.
6. Field-party members become unavailable to base systems.
7. Morale, injury, death, or road disruptions can interrupt assignments.

## Existing System Integration

- `game/game_state.py`: daily tick owner.
- `game/entities/registry.py`: member availability and labor components.
- `game/systems/movement_system.py`: field-party movement.
- `game/systems/ai_system.py`: base NPC labor behaviors.
- `game/systems/morale_system.py`: can block or alter assignments.
- `game/systems/research_system.py`: consumes scholar/archive labor.
- `game/systems/infrastructure_system.py`: consumes road/Waystation labor.

## Minimum Viable Version

- Assign members to Food, Water, Shelter, Guard, Research, Road Clearing, Rest, or Field Party.
- Each assignment produces deterministic daily deltas.
- Field-party membership removes base labor contribution.

## Later Expansion

- Partial-day scheduling.
- Companion objections/refusals.
- Assignment synergies between spouses.
- Tool-specific modifiers.
- Night events generated from assignment risks.

---

# 6. Proposed System: Base Camp and Walkable Consequence Engine

## Purpose

Make the settlement a physical, inspectable, evolving place rather than a menu. Base state should be visible in map layout, NPC behavior, lighting, project sites, storage, graves, and Archive activity.

## Source of Truth

- `game/game_state.py` owns BaseCamp state.
- `game/world/game_map.py` owns walkable terrain.
- `game/entities/registry.py` owns BaseCamp, buildings, project sites, storage, NPCs, and items.

## Proposed Modules

- `game/systems/base_camp_system.py`
- `game/expedition/base_camp.py`
- `game/world/base_layout.py`
- `engine/render_base_camp_overlays.py` or integrated renderer overlay hooks

## Proposed Components

```python
BaseCamp(
    camp_id: int,
    location_id: int,
    founded_turn: int,
)

CampResourceState(
    food: float,
    water: float,
    shelter: float,
    security: float,
    health: float,
    morale: float,
)

Facility(
    facility_type: str,  # archive, storehouse, infirmary, workshop, watch post
    condition: float,
    active: bool,
)

Storage(
    contents: dict[str, int],
)
```

## Data Flow

1. Harbor generation marks a ruined port site as the initial BaseCamp location.
2. BaseCamp entity is spawned.
3. Buildings/facilities are represented as entities or map features.
4. Assignments modify facility state and resources.
5. Renderer displays visible camp changes.
6. Interaction system allows the player to physically visit Archive, storehouse, infirmary, graves, workshop, and planning table.

## Existing System Integration

- `engine/renderer.py`: displays physical base state from viewport render inputs.
- `engine/render_lighting.py`: handles camp lighting, night watch, hidden-light lantern effects.
- `game/systems/sound.py`: ambient and event sound.
- `game/systems/research_system.py`: Archive facility.
- `game/systems/morale_system.py`: visible grief/refusal states.
- `game/entities/registry.py`: base facility entities and storage.
- Runtime scheduler: base labor, guard shifts, construction, grief behavior, nightly events, torch fuel, and delayed consequences become scheduled actions rather than ad hoc frame or broad-turn updates.
- `EventBatch`: facility work, storage changes, grief events, camp alarms, and visible construction changes produce structured events for logs, AI, sound, and rendering.

## Minimum Viable Version

- Ruined harbor with BaseCamp entity.
- Inspectable facilities.
- Resource state updates daily.
- Visual condition changes for at least shelter, storage, Archive, and graves.

## Later Expansion

- Dynamic NPC schedules.
- Construction sites visible on map.
- Camp lighting/security behavior.
- Walkable debates/events.
- Physical deposition of artifacts and KnowledgeFragments.

---

# 7. Proposed System: Central Archive and Eureka Synthesis

## Purpose

Require the expedition to physically return to base camp to synthesize isolated field discoveries into actionable mechanics. This implements “Knowledge as Loot.”

## Source of Truth

- Archive component on the immutable BaseCamp entity.
- `game/systems/research_system.py` owns synthesis logic.
- Data tables own recipe definitions.

## Proposed Modules

- `game/systems/research_system.py`
- `game/research/models.py`
- `game/research/recipes.py`
- `data/research/eureka_recipes.yaml`
- `data/research/concepts.yaml`

## Proposed Components

```python
KnowledgeFragment(
    fragment_id: str,
    fragment_type: str,
    source_location_id: int,
    tags: tuple[str, ...],
    quality: float,
)

Archive(
    fragments: set[str],
    concepts: set[str],
    active_projects: set[str],
)

ResearchProject(
    project_id: str,
    required_fragments: tuple[str, ...],
    required_roles: tuple[str, ...],
    scholar_hours_required: float,
    progress: float,
)

Concept(
    concept_id: str,
    unlock_type: str,
    payload_ref: str,
)
```

## Data Flow

1. Player investigates a field object, ruin, body, inscription, road marker, cave feature, or survivor practice.
2. The interaction generates a `KnowledgeFragment`.
3. Fragment is carried by the player, a companion, or in expedition storage.
4. Player physically returns to BaseCamp.
5. Player interacts with the Archive.
6. Fragment transfers into the Archive component.
7. `research_system.py` runs a daily tick.
8. The system cross-references Archive fragments, assigned labor, required tools, and recipe tables.
9. Matched recipes generate `Concept` unlocks.
10. Concepts unlock actions, translations, field procedures, hybrid tools, route confidence, or new research projects.

## Existing System Integration

- `game/entities/registry.py`: stores fragment components and Archive state.
- `game/game_state.py`: daily tick and global unlocks.
- `game/systems/expedition_assignment_system.py`: assigns scholars, archivists, practical mages, craftspeople.
- `game/systems/infrastructure_system.py`: road and Waystation concepts unlock new construction actions.
- `magic/` and `game/effects/`: Concepts can unlock hybrid magical tools.
- `engine/`: Archive UI and physical interactions.
- `data/`: research recipes and concept definitions.

## Minimum Viable Version

- Fragment pickup.
- Archive deposit interaction.
- Recipe table checks exact fragment tags.
- Concept unlock produces one new action or route.

## Later Expansion

- Partial evidence quality.
- Conflicting interpretations.
- Companion expertise modifying research.
- Dangerous experiments.
- Political choices over what to report, hide, preserve, or seal.
- Multiple research queues.

---

# 8. Proposed System: Infrastructure, Ancient Roads, and Waystations

## Purpose

Force the player to physically secure and travel Ancient Roads, making the surface campaign a logistical and historical core loop rather than a fast-travel layer.

## Source of Truth

- `worldgen/` owns macro road generation.
- `game/world/game_map.py` owns generated terrain and walkable map state.
- `game/systems/infrastructure_system.py` owns mutable infrastructure state.
- `pathfinding/` and `game/systems/pathfinding/flowfield.py` consume travel costs.

## Proposed Modules

- `worldgen/overland_core.py`
- `worldgen/road_graph.py`
- `game/systems/infrastructure_system.py`
- `game/infrastructure/models.py`
- `data/infrastructure/projects.yaml`

## Proposed Components

```python
Infrastructure(
    infra_type: str,  # ancient_road, bridge, culvert, waystation, marker
    condition: float,
    active: bool,
)

TravelModifier(
    cost_multiplier: float,
    safety_modifier: float,
    scent_modifier: float,
)

RoadSegment(
    road_id: str,
    from_node_id: str,
    to_node_id: str,
    survey_state: str,
    clear_state: str,
)

Waystation(
    waystation_id: str,
    road_segment_id: str,
    supply_capacity: float,
    scent_output: float,
    maintenance_need: float,
)
```

## Data Flow

1. `worldgen/overland_core.py` generates macro terrain and POIs.
2. Road graph generation connects major POIs with Ancient Roads.
3. Road tiles receive terrain tags and default travel modifiers.
4. Player discovers road segments through exploration.
5. Player assigns workers to clear, repair, mark, or secure segments.
6. `infrastructure_system.py` mutates road segment state and travel costs.
7. Pathfinding grids update.
8. AI supply carriers and field parties prefer secured lower-cost routes.
9. Waystations extend supply range but generate maintenance needs and scent pressure.

## Existing System Integration

- `worldgen/topology_cube_sphere.py`: macro coordinate frame and world topology.
- `worldgen/`: future source of overland regions, roads, POIs.
- `game/world/game_map.py`: terrain and walkability.
- `game/systems/pathfinding/flowfield.py`: movement cost and route preference.
- `game/systems/expedition_assignment_system.py`: road labor assignments.
- `game/systems/overland_threat_system.py`: scent and threat pressure.
- `game/entities/registry.py`: road markers, blockages, and Waystation entities.
- `engine/renderer.py`: visible road state and Waystation overlays.
- Runtime scheduler: travel, road clearing, delayed blockages, repair work, patrols, supply carriers, and Waystation maintenance are scheduled actions.
- Dirty state: road or bridge changes mutate movement-cost, walkability, scent, and visibility-related arrays only where affected.
- `EventBatch`: blockage, clearing, ambush, repair, supply arrival, and route discovery events can pause travel/rest/fast-forward through importance thresholds.

## Minimum Viable Version

- Generate one Ancient Road from harbor to first inland site.
- Road can be blocked, cleared, and marked.
- Waystation can be built at one road node.
- Cleared road reduces travel cost and increases safe expedition range.

## Later Expansion

- Full road graph.
- Branches and false leads.
- Bridges/culverts.
- Road shrines.
- Spatially scarred road segments.
- Dynamic weather damage.
- Supply caravans.
- Predator exploitation of travel routes.

---

# 9. Proposed System: Overland Scent-Gradient Threats

## Purpose

Replace generic random wilderness danger with legible predator pressure emerging from scent, travel, food, carcasses, smoke, and supply-line behavior.

## Source of Truth

- `pathfinding/perception_systems.py` owns scent/noise flow concepts.
- `game/perception.py` or `game/ai/perception.py` bridges production perception state.
- `game/systems/overland_threat_system.py` owns threat updates.
- `game/world/game_map.py` owns regional scent fields.

## Proposed Modules

- `game/systems/overland_threat_system.py`
- `game/overland/scent_sources.py`
- `game/overland/predator_state.py`
- Extensions to `pathfinding/perception_systems.py` only when generic flow behavior is needed.

## Proposed Components

```python
ScentSource(
    source_type: str,  # base_camp, waystation, field_party, carcass, supply_cache
    strength: float,
    decay_rate: float,
)

PredatorTerritory(
    predator_id: int,
    home_region_id: str,
    hunger: float,
    tracking_sensitivity: float,
)

ThreatIntent(
    target_kind: str,
    target_location: tuple[int, int],
    confidence: float,
)
```

## Data Flow

1. BaseCamp, Waystations, field parties, kills, food caches, and supply routes emit scent.
2. Scent fields update on a daily or regional tick, not every frame.
3. Predators sample scent gradients within active regions.
4. Predator GOAP or simple behavior chooses hunt, investigate, stalk, avoid, or attack.
5. Pathfinding moves predators toward high-value scent gradients.
6. The player receives clues: tracks, missing carcasses, disturbed markers, animal calls, companion warnings.
7. If ignored, predators threaten Waystations, supply carriers, field parties, or camp.

## Existing System Integration

- `pathfinding/perception_systems.py`: flow field algorithms and scent concepts.
- `game/ai/perception.py`: perception snapshots if predators become actor AI.
- `game/ai/strategy.py`: behavior selection.
- `game/systems/pathfinding/flowfield.py`: route choice.
- `game/systems/sound.py`: animal calls and warning cues.
- `game/systems/infrastructure_system.py`: Waystations as scent sources.
- `engine/renderer.py`: optional tracks/traces overlays.
- Runtime scheduler: scent field diffusion, predator sampling, stalking, attacks, and clue generation are scheduled at explicit ticks.
- Dense perception fields: scent and noise remain dense or regional arrays, while AI consumes sparse facts such as heard sound, smelled supply route, saw campfire, found carcass, or lost trail.
- `EventBatch`: predator pressure emits visible and non-visible events with importance levels, allowing travel/rest/fast-forward to pause on tracks, calls, damage, missing supplies, or hostile sightings.

## Minimum Viable Version

- Base camp emits scent.
- One predator follows a coarse scent map.
- Player can infer approach through tracks and warning events.
- Scent masking or route change reduces risk.

## Later Expansion

- Multiple predator species.
- Wind/weather scent behavior.
- Carcass and smoke interactions.
- Predators learning route patterns.
- Siege-like camp pressure.
- Prey/herd simulation.

---

# 10. Proposed System: Social Morale and Bonds

## Purpose

Make the expedition socially consequential, especially through the Couples Draft. A death, absence, failure, or frightening discovery should alter labor, trust, and behavior.

## Source of Truth

- `game/entities/registry.py` stores relationships and mental state.
- `game/systems/morale_system.py` processes events and daily morale.
- `game/ai/` consumes morale state for production behavior.

## Proposed Modules

- `game/systems/morale_system.py`
- `game/social/models.py`
- `game/social/events.py`
- Optional future bridge from top-level `ai/` R&D concepts into `game/ai/`.

## Proposed Components

```python
MentalState(
    stress_level: float,
    morale_state: str,  # steady, shaken, grieving, panicked, defiant, inspired
    trust_in_leader: float,
    fear_tags: tuple[str, ...],
)

SocialBond(
    target_entity_id: int,
    bond_type: str,
    strength: float,
)

GriefState(
    lost_entity_id: int,
    grief_stage: str,
    started_turn: int,
    work_penalty: float,
)
```

## Data Flow

1. A combat, death, injury, night event, assignment, or discovery emits an event.
2. `morale_system.py` receives the event.
3. The system queries SocialBond components.
4. Affected entities receive stress, grief, fear, trust, or morale changes.
5. MentalState modifies assignment validity and autonomous behavior.
6. `game/ai/` reads MentalState and chooses labor, grieving, refusal, wandering, volunteering, guarding, or argument.
7. UI and renderer show visible consequences in base behavior.

## Existing System Integration

- `game/systems/death_system.py`: emits death events.
- `game/systems/combat_system.py`: injuries and violence events.
- `game/entities/registry.py`: components and relationships.
- `game/systems/ai_system.py`: scheduling.
- `game/ai/`: production behavior.
- `auto/`: can remain a tuning harness for morale-aware GOAP prototypes.
- `ai/`: community AI R&D can inform later promoted behavior.
- `game/systems/expedition_assignment_system.py`: blocks or modifies assignments.
- `EventBatch`: death, injury, fear, refusal, discovery, and argument events drive morale updates.
- Runtime scheduler: grief, refusal, recovery, guard duty, field travel, and base labor all consume explicit simulation time.

## Minimum Viable Version

- Spouse death causes grief state.
- Grieving survivor loses labor availability for a set period or until a recovery condition.
- Trust/morale UI reports the cause.

## Later Expansion

- Grief behaviors.
- Refusals.
- Ritual demands.
- Rivalries.
- Ideological splits.
- Leadership decisions that alter trust.
- Morale-aware GOAP cost reweighting.

---

# 11. Proposed System: Morale-Aware GOAP and Labor Behavior

## Purpose

Connect social state to autonomous labor behavior so morale is not just a dashboard stat.

## Source of Truth

- Production gameplay AI belongs under `game/ai/`.
- `auto/` remains a simulation/tuning harness for experimental GOAP behavior.
- `game/systems/ai_system.py` schedules AI turns.

## Proposed Modules

- `game/ai/labor_goap.py`
- `game/ai/morale_adapter.py`
- `auto/` prototypes only for tuning.
- `game/systems/ai_system.py` integration hooks.

## Proposed Data

```python
LaborGoal(
    goal_type: str,  # farm, build, research, guard, grieve, rest, refuse
    base_priority: float,
)

MoraleCostModifier(
    action_type: str,
    multiplier: float,
    reason: str,
)
```

## Data Flow

1. `morale_system.py` updates MentalState.
2. `game/ai/morale_adapter.py` converts MentalState into GOAP cost modifiers.
3. Production AI evaluates labor actions.
4. High stress increases cost of normal labor and lowers cost of grief/rest/refusal behaviors.
5. Assignment system reacts when a worker does not perform assigned work.
6. Base consequences propagate to resources, projects, Archive progress, and infrastructure.

## Existing System Integration

- `game/ai/goap.py`: production GOAP.
- `game/ai/goap_adapter.py`: state-to-GOAP bridge.
- `game/systems/ai_system.py`: turn processing.
- `game/systems/morale_system.py`: mental state source.
- `auto/goap_engine.py`: optional testbed for learning/tuning, not production import target.

## Minimum Viable Version

- Convert stress into work-efficiency penalty.
- Critical stress triggers “unavailable/grieving” behavior.
- Assignment report explains failure.

## Later Expansion

- Full GOAP labor behavior.
- Weighted refusals.
- Recovery actions.
- Companion support actions.
- Social interventions by the player.

---

# 12. Proposed System: Wildness Gradient / Doom Engine Pressure

## Purpose

Mechanically represent the widening of magical tolerances as the player moves closer to the continental epicenter, enabling organic hybridization of cultural magic interfaces and stable anomalies.

## Source of Truth

- `worldgen/` designates the Doom Engine epicenter.
- `game/systems/wildness_gradient.py` owns runtime gradient queries.
- `magic/` and `game/effects/` consume gradient values.
- `game/world/game_map.py` stores region/chunk mapping.

## Proposed Modules

- `game/systems/wildness_gradient.py`
- `worldgen/phase_sites.py`
- `game/magic/tolerance.py`
- Optional `data/magic/phase_regions.yaml`

## Proposed Components / State

```python
GradientField(
    epicenter: tuple[int, int],
    min_multiplier: float,
    max_multiplier: float,
)

GradientModifier(
    base_multiplier: float,
    formula_tolerance_delta: float,
    hybridization_delta: float,
)
```

## Data Flow

1. World generation designates Doom Engine coordinate.
2. `wildness_gradient.py` computes a deterministic region/coordinate field.
3. Field values are stored as dense arrays or region summaries.
4. Magic execution queries the caster/tool/global coordinate.
5. The gradient adjusts tolerance bounds, not raw power by default.
6. Research and Archive systems can reveal the existence of the gradient gradually.

## Existing System Integration

- `worldgen/topology_cube_sphere.py`: macro coordinate system.
- `game/world/game_map.py`: map coordinate lookup.
- `magic/executor.py`: spell/tool execution.
- `game/effects/handlers.py`: applies final effects.
- `research_system.py`: unlocks knowledge of gradient.
- `engine/render_lighting.py`: optional visual distortion/phase overlays later.
- `utils.game_rng.GameRNG`: any stochastic anomaly generation.

## Minimum Viable Version

- Region tag: Coastal, Inland, Deep Inland, Epicenter-Adjacent.
- Each tag maps to a small tolerance modifier.
- Magic tool checks read region tag.

## Later Expansion

- Dense Numba field.
- Distance transform from epicenter.
- Multiple scars/sanctuaries.
- Ghost Term interaction.
- Dynamic regional changes.

---

# 13. Proposed System: Magic Hybridization and Comparative Thaumaturgy

## Purpose

Allow the player to discover that different cultures access the same deterministic magical law through different interfaces, and that widening wildness tolerance enables cross-cultural hybrid tools and practices.

## Source of Truth

- `magic/` owns internal magical execution.
- `game/systems/research_system.py` owns discovery of hybrid Concepts.
- `data/magic/` owns cultural interface definitions.
- `game/effects/` owns applied outcomes.

## Proposed Modules

- `magic/cultural_interfaces.py`
- `magic/hybridization.py`
- `game/magic/tool_registry.py`
- `data/magic/cultural_interfaces.yaml`
- `data/magic/hybrid_recipes.yaml`

## Proposed Data

```python
CulturalInterface(
    interface_id: str,
    channels: tuple[str, ...],  # inscription, song, breath, gesture, geometry
    tolerance_profile: dict[str, float],
)

HybridPractice(
    hybrid_id: str,
    required_concepts: tuple[str, ...],
    required_site_tags: tuple[str, ...],
    failure_modes: tuple[str, ...],
)
```

## Data Flow

1. Field discoveries create KnowledgeFragments tagged with interface clues.
2. Central Archive synthesizes Concepts about cultural interfaces.
3. Concepts unlock hybrid recipes or tool modifications.
4. Magic execution checks tool/interface requirements.
5. Wildness Gradient widens tolerance where appropriate.
6. Successful hybridization unlocks practical field effects.

## Existing System Integration

- `magic/`: backend representation.
- `scripting_engine.py`: possible internal spell/effect representation.
- `game/effects/`: final effects.
- `research_system.py`: unlocks hybrid Concepts.
- `wildness_gradient.py`: modifies tolerance.
- `game/systems/cave_survey_system.py`: identifies acoustic/geometry/breath clues.

## Minimum Viable Version

- Tags and recipe checks.
- One hybrid tool unlocked by Archive synthesis.
- Region tolerance affects success threshold.

## Later Expansion

- Multi-channel hidden deterministic model.
- Partial failures.
- Tool repair and cultural misinterpretation.
- Scholar disagreement.
- Dangerous experiments.

---

# 14. Proposed System: Ghost Term and Phase Pressure

## Purpose

Represent the hidden deficit produced by formulaic ordered magic and connect it to the larger order/wildness cosmology.

## Source of Truth

- `magic/` emits Ghost Term events when formulaic magic is used.
- `game/systems/ghost_term_system.py` aggregates local/regional load.
- `wildness_gradient.py` and Archive research consume the resulting state.

## Proposed Modules

- `game/systems/ghost_term_system.py`
- `magic/ghost_term.py`
- `data/magic/ghost_term_rules.yaml`

## Proposed State

```python
GhostTermLoad(
    location_id: int,
    accumulated_load: float,
    decay_rate: float,
    saturation_state: str,
)

PhaseRegion(
    region_id: str,
    order_rigidity: float,
    wildness_tolerance: float,
    ghost_term_load: float,
)
```

## Data Flow

1. Magic executor completes formulaic ordered effect.
2. It emits GhostTermEvent with effect scale and location.
3. `ghost_term_system.py` adds load to local/regional phase state.
4. High load modifies future magic reliability, anomaly risk, or research clues.
5. Archive can synthesize Ghost Term Concepts from repeated observations.
6. Doom Engine Gradient and sanctuary sites can alter accumulation or bleed-off.

## Existing System Integration

- `magic/executor.py`: event source.
- `game/effects/handlers.py`: effect scale.
- `wildness_gradient.py`: phase interaction.
- `research_system.py`: discovery.
- `game/world/game_map.py`: location/region mapping.
- `engine/renderer.py`: optional visible overlays only after discovery.

## Minimum Viable Version

- Track Ghost Term as hidden regional counter.
- Certain magic uses increment it.
- Research can reveal it.

## Later Expansion

- Dynamic phase fields.
- Ghost-Term saturated caves.
- Magical scars.
- Deficit bleed-off sites.
- Ritual management.

---

# 15. Proposed System: Practical Magical Tools

## Purpose

Make magic player-facing as tools, procedures, repairs, and discoveries rather than a programming puzzle or generic combat spell list.

## Source of Truth

- `game/items/` owns item/tool records.
- `magic/` owns tool behavior and backend execution.
- `game/effects/` applies outcomes.
- `research_system.py` unlocks repairs and hybrid variants.

## Proposed Modules

- `game/magic/practical_tools.py`
- `game/items/magical_tools.py`
- `data/items/magical_tools.yaml`
- `data/magic/tool_effects.yaml`

## Proposed Components

```python
MagicalTool(
    tool_id: str,
    interface_id: str,
    condition: float,
    known: bool,
    bound_entity_id: int | None,
)

ToolProcedure(
    procedure_id: str,
    required_concepts: tuple[str, ...],
    required_roles: tuple[str, ...],
)
```

## Examples

- Hidden-light lantern.
- Fuel-less flame.
- Remembering rope.
- Water-finding rod.
- Inscription-revealing lens.
- Preservation chest.
- Scent-masking clay.
- Sound-casting bell.
- Path-marking chalk.
- Breath-stilling charm.
- Air-testing flame.
- Stone-reading tool.
- Warding nails.
- Disease-slowing bandage.
- Translation lens.
- Memory lamp.
- Route cord.
- Boundary marker.
- Weather glass.
- Oath-stone.

## Existing System Integration

- `game/items/registry.py`: item/tool storage.
- `magic/`: execution logic.
- `game/effects/`: outcomes.
- `engine/render_lighting.py`: light-emitting tools.
- `pathfinding/perception_systems.py`: scent/sound-related tools.
- `research_system.py`: unlocks and repairs.
- `expedition_assignment_system.py`: tool allocation removes base availability.

## Minimum Viable Version

- Hidden-light lantern.
- Scent-masking clay.
- Inscription lens.
- Tool availability affects base or field.

## Later Expansion

- Tool binding.
- Wear/damage.
- Repairs from Archive Concepts.
- Hybrid cultural upgrades.
- Dangerous misuses.

---

# 16. Proposed System: Cave Survey and Stratigraphy

## Purpose

Make caves archives rather than generic dungeon levels. The player classifies caves through survey, reads layers, and distinguishes natural, animal, refuge, civic, ritual, and deep-time use.

## Source of Truth

- `Dungeon/` generates cave structure.
- `game/world/game_map.py` stores cave map state.
- `game/systems/cave_survey_system.py` owns survey state.
- `research_system.py` consumes cave evidence.

## Proposed Modules

- `game/systems/cave_survey_system.py`
- `game/caves/stratigraphy.py`
- `data/caves/cave_types.yaml`
- `data/caves/evidence_tags.yaml`

## Proposed Components

```python
CaveSurvey(
    cave_id: str,
    survey_level: int,
    known_tags: set[str],
    risk_tags: set[str],
)

StratigraphyLayer(
    layer_type: str,  # geological, ancient, refuge, post_calamity, prior_expedition
    confidence: float,
    evidence_refs: tuple[str, ...],
)

CaveEvidence(
    evidence_id: str,
    evidence_type: str,
    layer_type: str,
    fragment_id: str | None,
)
```

## Data Flow

1. Dungeon generation produces cave maps with geometry/depth/chambers.
2. Cave survey system tags locations with evidence.
3. Player/companions inspect airflow, water, smoke, inscriptions, tool marks, acoustics, bones, and altered geometry.
4. Survey state records what is known.
5. Important evidence generates KnowledgeFragments.
6. Archive synthesis turns cave evidence into Concepts.

## Existing System Integration

- `Dungeon/core.py`, `Dungeon/processor.py`, `Dungeon/shaper.py`: cave generation.
- `game/world/game_map.py`: tile/map storage.
- `game/world/fov.py`, `game/world/los.py`, `game/world/light_fov.py`: cave visibility.
- `engine/render_lighting.py`: light behavior.
- `pathfinding/perception_systems.py`: sound/scent cave behavior.
- `research_system.py`: cave evidence into knowledge.
- `expedition_assignment_system.py`: specialists affect survey quality.
- Dense opacity and height planes: smoke, glass, mist, foliage, cave mouths, low ceilings, shafts, large creatures, and partial barriers should affect visibility without replacing the map with cell objects.
- Side-aware lighting: cave walls, ledges, openings, and carved surfaces can receive directional light and memory tinting, producing clearer scenes in visually dense caves.

## Minimum Viable Version

- Cave categories.
- Survey action.
- Evidence tags.
- One KnowledgeFragment per meaningful cave clue.

## Later Expansion

- Layered procedural archaeology.
- Excavation risk.
- Context destruction.
- Companion disagreements.
- Deep-time inference chains.

---

# 17. Proposed System: Persistent Scars and Anomaly Rules

## Purpose

Represent stable consequences of the five-year reality break as learnable biological, spatial, magical, and cultural scars.

## Source of Truth

- `worldgen/` and `Dungeon/` generate scar locations.
- `game/world/game_map.py` stores anomaly tags.
- `game/systems/anomaly_system.py` owns runtime rules.
- `research_system.py` discovers scar rules.

## Proposed Modules

- `game/systems/anomaly_system.py`
- `worldgen/anomaly_sites.py`
- `Dungeon/anomaly_features.py`
- `data/anomalies/scar_rules.yaml`

## Proposed Components

```python
PersistentScar(
    scar_type: str,  # biological, spatial, magical, cultural
    rule_id: str,
    discovered: bool,
)

AnomalyRule(
    rule_id: str,
    trigger_tags: tuple[str, ...],
    effect_ref: str,
    learnable: bool,
)
```

## Examples

- Stair has different count depending on direction.
- Road shorter when walked silently.
- Tool works better broken.
- Threshold rejects exact inscription but responds to song.
- Cave mouth easier to find when not directly searched.
- Horned lineage indicates hereditary calamity alteration.
- Settlement refuses to repair a crack because it is functional.

## Existing System Integration

- `game/world/los.py`, `light_fov.py`: spatial anomalies affecting visibility.
- `movement_system.py`: spatial/movement effects.
- `magic/`: magical scars and tool behavior.
- `research_system.py`: rule discovery.
- `morale_system.py`: cultural and social reactions.
- `engine/renderer.py`: subtle reveal overlays once learned.

## Minimum Viable Version

- Static anomaly tags.
- Triggered inspect text and one gameplay effect.
- Archive Concept reveals rule.

## Later Expansion

- Procedural scar generation.
- Biological lineages.
- Anomaly ecology.
- Rule inference UI.
- Dynamic interaction with Ghost Term.

---

# 18. Proposed System: Deep-Time Archaeology and Site History

## Purpose

Generate and track historical phases of sites so ruins, roads, and caves reveal layered human occupation rather than random content.

## Source of Truth

- `worldgen/` owns macro historical site placement.
- `Dungeon/` owns cave-site layers where applicable.
- `research_system.py` owns player understanding of history.

## Proposed Modules

- `worldgen/site_history.py`
- `game/history/site_records.py`
- `data/history/site_phase_templates.yaml`

## Proposed Data

```python
SiteHistory(
    site_id: str,
    phases: tuple[str, ...],
    collapse_sequence: str,
    known_confidence: float,
)

HistoricalEvidence(
    evidence_id: str,
    site_id: str,
    phase: str,
    fragment_id: str,
)
```

## Data Flow

1. Worldgen assigns phase templates to major sites.
2. Dungeon generation receives relevant cave/city/refuge tags.
3. Field survey exposes evidence.
4. KnowledgeFragments enter Archive.
5. Archive synthesizes phase Concepts.
6. Player updates map/history understanding.

## Existing System Integration

- `worldgen/`: macro POIs.
- `Dungeon/`: caves and cave settlements.
- `research_system.py`: evidence synthesis.
- `engine/renderer.py`: map notes/overlays.
- `game/ui`: journal/history interface.

## Minimum Viable Version

- Site phase tags.
- Evidence clusters.
- Archive unlocks “what happened here” summaries.

## Later Expansion

- Procedural stratigraphy.
- Competing interpretations.
- Prior expedition overlays.
- Simulated historical echoes.

---

# 19. Proposed System: Reveal Ladder and Campaign Progression

## Purpose

Structure progression through discoveries, Archive synthesis, road access, and field evidence instead of dungeon depth or character level.

## Source of Truth

- `game/game_state.py` owns campaign state.
- `research_system.py` owns Concept unlocks.
- `infrastructure_system.py` owns road/Waystation access.
- `game/campaign/reveal_ladder.py` owns reveal gates.

## Proposed Modules

- `game/campaign/reveal_ladder.py`
- `game/campaign/milestones.py`
- `data/campaign/reveal_ladder.yaml`

## Proposed Data

```python
RevealState(
    reveal_id: str,
    unlocked: bool,
    evidence_required: tuple[str, ...],
    consequences: tuple[str, ...],
)

CampaignMilestone(
    milestone_id: str,
    required_concepts: tuple[str, ...],
    required_locations: tuple[str, ...],
)
```

## Data Flow

1. Player discovers locations, evidence, and Concepts.
2. Reveal ladder evaluates prerequisites.
3. New campaign beats unlock routes, Archive projects, NPC reactions, anomalies, or tools.
4. Milestone progress affects world state and narrative pressure.

## Existing System Integration

- `research_system.py`: Concepts.
- `infrastructure_system.py`: route access.
- `cave_survey_system.py`: cave discoveries.
- `morale_system.py`: reactions.
- `game_state.py`: campaign flags.
- `engine`: UI/journal feedback.

## Minimum Viable Version

- Ordered reveal flags.
- Journal updates.
- Unlock next route/project.

## Later Expansion

- Branching reveal consequences.
- Faction/reporting decisions.
- False interpretations.
- Companion-specific reactions.

---

# 20. Proposed System: Companion Expertise and Interpretation

## Purpose

Make companions matter in the field and base by changing what the player can safely do, correctly interpret, and synthesize.

## Source of Truth

- `game/entities/registry.py` stores member roles and skills.
- Assignment and survey/research systems consume expertise.

## Proposed Modules

- `game/expedition/expertise.py`
- `game/systems/interpretation_system.py`
- `data/expedition/expertise_rules.yaml`

## Proposed Components

```python
ExpertiseProfile(
    expertise_tags: tuple[str, ...],
    base_modifier: float,
    field_modifier: float,
)

Interpretation(
    subject_id: str,
    confidence: float,
    interpreter_entity_id: int,
    result_fragment_id: str,
)
```

## Data Flow

1. Field object/cave/site requires interpretation.
2. System checks party expertise.
3. Appropriate companion increases confidence, reduces risk, or reveals hidden fragment.
4. Back at Archive, assigned specialists modify research speed and outcomes.
5. Wrong or absent expertise can produce incomplete fragments.

## Existing System Integration

- `cave_survey_system.py`: survey quality.
- `research_system.py`: synthesis.
- `expedition_assignment_system.py`: availability.
- `morale_system.py`: fear/trust can block expertise use.
- `game/skills/`: possible bridge for skill levels.

## Minimum Viable Version

- Role tags gate or modify survey actions.
- Scholar/mason/hunter/healer/practical mage each has clear utility.

## Later Expansion

- Conflicting interpretations.
- Companion field dialogue.
- Expertise growth.
- Trauma/fear affects interpretation.

---

# 21. Proposed System: Knowledge, Map, and Route Memory

## Purpose

Track what the expedition knows about geography, routes, risks, and history separately from what exists in the world.

## Source of Truth

- `game/world/memory.py` handles map memory and visual memory.
- Proposed `game/knowledge/expedition_memory.py` handles strategic knowledge.
- Archive and field systems feed it.

## Proposed Modules

- `game/knowledge/expedition_memory.py`
- `game/knowledge/map_notes.py`
- `data/knowledge/note_types.yaml`

## Proposed Data

```python
MapKnowledge(
    location_id: int,
    known_tags: set[str],
    confidence: float,
    last_verified_turn: int,
)

RouteKnowledge(
    route_id: str,
    safety_confidence: float,
    travel_cost_confidence: float,
    known_blockages: set[str],
)
```

## Data Flow

1. Exploration reveals map features.
2. Survey actions create notes.
3. Archive processing increases confidence.
4. Infrastructure and threat systems consume known routes and risks.
5. UI displays confirmed vs suspected knowledge.

## Existing System Integration

- `game/world/memory.py`: visual explored memory.
- `research_system.py`: knowledge confidence.
- `infrastructure_system.py`: road/route knowledge.
- `overland_threat_system.py`: predator clues.
- `engine/renderer.py`: map overlays.

## Minimum Viable Version

- Known/suspected route tags.
- Map notes for discoveries.
- Archive upgrades confidence.

## Later Expansion

- False leads.
- Outdated information.
- Companion map disagreements.
- Prior expedition map integration.

---

# 22. Proposed System: Surface Ecology and Local Resource Survey

## Purpose

Make surface exploration matter before dungeon depth by requiring the expedition to survey water, food, timber, clay, stone, game trails, predator territories, and disease sources.

## Source of Truth

- `worldgen/` generates local resource distribution.
- `game/world/game_map.py` stores terrain/resource features.
- `expedition_assignment_system.py` assigns survey work.
- `overland_threat_system.py` consumes predator/ecology state.

## Proposed Modules

- `worldgen/local_resources.py`
- `game/systems/local_survey_system.py`
- `data/world/resources.yaml`

## Proposed Components

```python
ResourceNode(
    resource_type: str,
    yield_rate: float,
    depletion_state: float,
    known: bool,
)

SurveyTask(
    survey_type: str,
    target_area_id: str,
    progress: float,
)
```

## Data Flow

1. Worldgen creates local resources and hazards.
2. Player assigns scouts/hunters/naturalists.
3. Survey reveals nodes, risks, or false assumptions.
4. Resource systems modify base food/water/shelter projects.
5. Predator and scent systems react to hunting and carcasses.

## Existing System Integration

- `worldgen/`: generation.
- `game/world/game_map.py`: resource placement.
- `expedition_assignment_system.py`: labor.
- `overland_threat_system.py`: predator pressure.
- `research_system.py`: some discoveries become KnowledgeFragments.

## Minimum Viable Version

- Discover water, food, timber, and predator territory.
- Survey results modify daily resource production and danger.

## Later Expansion

- Seasonal changes.
- Overhunting.
- Disease ecology.
- Plant identification.
- Weather impacts.

---

# 23. Proposed System: Turn-Authoritative Array Runtime and Visual Composition

## Purpose

Give the Lost Continent Expedition engine a single deterministic runtime path that
supports manual turns, variable actor speeds, rest, travel, observation mode,
fast-forward simulation, deterministic replay, dynamic lighting, fog of war,
memory, scent, sound, perception fields, and smooth visual transitions.

This is not a separate content feature. It is the implementation spine that lets
the other proposed systems become visually rich and performant without creating
renderer-owned gameplay rules or per-frame simulation shortcuts.

The architecture should make visually complex scenes cheaper and more legible:

- Campfires, hidden-light lanterns, Archive lamps, torches, smoke, Waystation markers, cave shafts, remembered terrain, moving entities, predator clues, and UI overlays can compose into one viewport output.
- FOV, lighting, sound, scent, memory, and pathing can share dense arrays and dirty regions instead of each scanning gameplay objects independently.
- Travel, rest, and fast-forward can run many correct simulation steps while coalescing cosmetic presentation work.

## Source of Truth

- Runtime scheduler owns authoritative simulation time.
- `game/` systems own authoritative state mutation.
- `game/world/` owns map planes, FOV, LOS, visibility, memory, and world-derived arrays.
- `game/entities/registry.py` owns entities and component records.
- `pathfinding/perception_systems.py` owns reusable sound/scent/flow concepts.
- `engine/` owns composition, lighting presentation, overlays, and platform drawing.
- `utils.game_rng.GameRNG` remains the canonical randomness API for all stochastic gameplay.

## Proposed Modules

- `game/runtime/scheduler.py`
- `game/runtime/policy.py`
- `game/runtime/events.py`
- `game/runtime/turn_result.py`
- `game/runtime/dirty_state.py`
- `game/world/opacity.py`
- `game/world/perception_fields.py`
- `game/world/knowledge_planes.py`
- `engine/viewport_input.py`
- `engine/visual_composer.py`
- `engine/animation_tables.py`

Existing modules should be adapted gradually; this proposal does not require a
single rewrite.

## Scheduler Model

Use a deterministic next-tick energy scheduler with compact state:

```text
sched_actor_id: int32[n]
entity_id: int32[n] # -1 for non-entity schedulables
kind: uint16[n] # player, monster, environmental, zone, timed effect
next_tick: int64[n]
base_speed: int16[n]
status_speed_delta: int16[n]
is_active: bool[n]
sequence: int64[n] # deterministic tie-breaker
```

The scheduler selects the active row with the lowest (next_tick, sequence) pair.

After an action resolves:

```text
next_tick += action_delay
sequence += 1
```

Action delays can represent:

- wait
- floor movement
- rubble movement
- quick weapon attack
- heavy weapon attack
- torch fuel burn
- poison tick
- fire spread
- predator scent sample
- road repair work
- field-party travel
- zone update

Effective speed modifies delay:

```text
effective_delay = base_action_delay * BASE_SPEED / effective_speed
```

This supports haste, slow, encumbrance, terrain costs, weapon speed, casting time,
labor cadence, travel pacing, recovery time, paralysis, delayed effects, and
environmental timing through one deterministic model.

## Runtime Policies

Runtime policy should be scalar data, not separate simulation loops:

```text
mode: uint8
auto_wait_player: bool
auto_continue_path: bool
turns_per_second: float32
max_steps_per_frame: int16
render_every_n_steps: int16
pause_threshold: uint8
pause_flags: uint32
allow_animation_skip: bool
```

Important events interrupt automation:

- TRIVIAL = 0
- AMBIENT = 1
- INTERESTING = 2
- THREATENING = 3
- CRITICAL = 4

Examples:

```text
REST:
  inject WaitAction until target complete
  pause on hostile seen, damage, nearby hazard, important sound, visible terrain change

TRAVEL:
  inject next path MoveAction
  pause on path blocked, hostile seen, new item, trap, damage, manual input

FAST_FORWARD:
  run real scheduler steps
  coalesce cosmetic animation
  render every N steps
  always pause/render on important event
```

## Authoritative State Layout

Map state should remain array-backed:

- tiles: uint16[h, w]
- feature_type: uint16[h, w]
- walkable: bool[h, w]
- transparent: bool[h, w]
- terrain_opacity: float32[h, w]
- entity_opacity: float32[h, w]
- effect_opacity: float32[h, w]
- total_opacity: float32[h, w]
- height_map: int16[h, w]
- ceiling_map: int16[h, w]
- light_channel_mask: uint32[h, w]
- movement_cost: uint16[h, w]
- terrain_flags: uint32[h, w]
- scene_geometry_version: int64

Compatibility with current boolean transparency:

```text
transparent = total_opacity < OPAQUE_THRESHOLD
```

The key transition is from wall/floor transparency alone to layered opacity:

```text
terrain opacity + entity opacity + effect opacity
```

This enables smoke, glass, mist, foliage, large monsters blocking partial sight,
force barriers, magic-only occlusion, sound-blocking but light-transparent
surfaces, and telepathy ignoring ordinary opacity without turning the map into an
object grid.

Entity state should continue to use registry/table ownership, with hot spatial
data mirrored as arrays:

- entity_id: int32[n]
- x: int16[n]
- y: int16[n]
- z_or_height: int16[n]
- glyph: uint16[n]
- fg_rgb: uint8[n, 3]
- blocks_movement: bool[n]
- opacity: float32[n]
- light_id: int32[n]
- ai_type: uint16[n]
- is_active: bool[n]
- hp: int16[n]
- max_hp: int16[n]

Derived occupancy planes should be updated incrementally:

- entity_block_count: uint16[h, w]
- entity_opacity: float32[h, w]
- top_entity_id: int32[h, w]

Movement touches only old and new cells, marks those cells dirty, updates opacity
if needed, and emits an `EntityMoved` event.

## Lighting, FOV, and Perception

Lighting should remain array-based and preserve side-aware, per-light cached
directional behavior.

Light source table:

- light_id: int32[n]
- owner_entity_id: int32[n]
- x: int16[n]
- y: int16[n]
- height: float32[n]
- radius: int16[n]
- intensity: float32[n]
- rgb: uint8[n, 3]
- direction: float32[n]
- cone_angle: float32[n]
- cone_softness: float32[n]
- channels: uint32[n]
- layer: uint8[n]
- param_version: int64[n]
- is_active: bool[n]

Separate lighting layers:

- SIMULATION # gameplay-relevant visibility and detection
- TRANSIENT # presentation-only flashes, sparks, flares
- UI # targeting, path, cursor, survey overlays

Only SIMULATION lights affect gameplay unless a presentation effect is explicitly
promoted into a simulation event.

Visibility output should be dense:

- visible_mask: bool[h, w]
- visibility_coeff: float32[h, w]
- visible_sides: uint8[h, w]
- distance: int16[h, w]

Special senses should use channel-filtered opacity arrays rather than one-off
visibility algorithms:

- ordinary vision -> opacity includes walls/smoke
- telepathy -> opacity ignores ordinary terrain
- sound -> opacity uses sound-blocking materials
- scent -> opacity uses scent flow rules
- magic sight -> opacity uses magic-channel barriers

Dense propagation fields should be separated from sparse AI facts:

- player_visible: bool[h, w]
- player_visibility_coeff: float32[h, w]
- player_visible_sides: uint8[h, w]
- noise_cost: int32[num_flows, h, w]
- scent_when: int32[h, w]

- observer_id: int32[n]
- subject_id: int32[n]
- fact_type: uint16[n]
- x: int16[n]
- y: int16[n]
- confidence: float32[n]
- channel: uint16[n]
- last_observed_tick: int64[n]
- flags: uint32[n]

AI should consume sparse facts and selected dense fields, not renderer state.

## Knowledge and Memory Planes

Player knowledge should be planes plus tables:

- known: bool[h, w]
- currently_visible: bool[h, w]
- remembered_tile: uint16[h, w]
- remembered_feature: uint16[h, w]
- remembered_height: int16[h, w]
- last_seen_tick: int64[h, w]
- memory_intensity: float32[h, w]
- memory_strength: float32[h, w]
- memory_flags: uint32[h, w]

Visual fading is presentation state. Gameplay memory is simulation state. A fade
animation must not erase authoritative expedition knowledge unless memory decay is
an intentional rule.

## Viewport Visual Composition

The renderer should move toward consuming a viewport input snapshot rather than
querying `GameState` and registries directly:

```python
@dataclass(slots=True)
class ViewportRenderInput:
    tiles: np.ndarray
    glyphs: np.ndarray
    fg: np.ndarray
    bg: np.ndarray
    visible: np.ndarray
    known: np.ndarray
    memory_intensity: np.ndarray
    height: np.ndarray
    light_rgb: np.ndarray
    side_rgba: np.ndarray | None
    animation_overlay_rgba: np.ndarray | None
    ui_overlay_rgba: np.ndarray | None
    dirty_mask: np.ndarray | None
```

Composition order:

1. out-of-bounds
2. unknown
3. remembered terrain
4. visible terrain
5. visible item/entity
6. simulation lighting
7. shadow/height/side tint
8. transient animation overlay
9. UI overlay
10. temporal interpolation

Final platform-facing arrays:

- glyph_or_tile: uint16[vp_h, vp_w]
- foreground_rgb: uint8[vp_h, vp_w, 3]
- background_rgb: uint8[vp_h, vp_w, 3]
- alpha: uint8[vp_h, vp_w]

Animations should be sparse tables plus overlay buffers. The simulation result
exists immediately; animation controls presentation only. Animation blocks input or
simulation only by explicit policy.

## Simulation-Derived Update Order

After each authoritative action, update derived systems in deterministic order:

1. occupancy and opacity planes
2. scene geometry version / dirty geometry
3. light source position and dirty light IDs
4. player/observer FOV if relevant
5. knowledge and memory planes
6. sound/scent/perception fields if relevant
7. AI perception facts if relevant
8. visual dirty masks/rects
9. event-derived animation queues

Dirty reasons decide which steps run. Not every action recomputes every derived
field.

## Migration Plan

Do not rewrite the engine around this in one pass.

### Phase A: Event Batch Spine

Add `EventBatch` and event importance.

Adapt current action handling to emit structured events while preserving current
behavior.

Bridge existing systems:

- message log reads events
- sound reads events
- dirty rendering reads events
- noise/scent can still use current queues initially

### Phase B: TurnResult Wrapper

Wrap current action + world advance in `TurnResult`.

Current behavior remains:

- player action
- advance_turn
- render

But outputs become structured:

- events
- changed entities
- changed cells
- dirty reasons
- dirty lights

### Phase C: Split Broad Turn Advancement

Break broad turn advancement into named deterministic stages:

- process_timed_events
- process_resources
- update_fov
- update_perception_fields
- step_community
- dispatch_ai
- process_zones
- update_sound_context

Do not change semantics yet.

### Phase D: Introduce Scheduler Incrementally

1. Add environmental, timed, and zone schedulables.
2. Move AI actors into the scheduler.
3. Move player input into queued scheduler intent.
4. Add runtime policies for manual, auto-wait, rest, travel, fast-forward, and paused.

### Phase E: Renderer Input Snapshot

Introduce `ViewportRenderInput`.

Move renderer code gradually away from direct `GameState` and registry inspection.

### Phase F: Opacity and Channel Expansion

Add float opacity planes behind the current `transparent` API.

Migrate lighting, FOV, and perception to channel-filtered opacity views where
useful.

## Minimum Viable Version

- `EventBatch` with event importance.
- `TurnResult` returned by existing player action / world advancement path.
- Dirty changed-cell and changed-entity arrays.
- Initial scheduler for timed/environmental actions.
- Renderer adapter that can accept `ViewportRenderInput` while preserving current rendered output.
- Boolean transparency remains compatible through `total_opacity < OPAQUE_THRESHOLD`.

## Later Expansion

- Full player/AI/environment energy scheduler.
- Travel, rest, observe, and fast-forward policies.
- Dense layered opacity.
- Channel-filtered FOV/perception.
- Incremental per-light dirty updates.
- Memory intensity visual fading.
- Animation overlay tables.
- Deterministic replay from initial state, scheduler state, RNG state, and event batches.

---

# 24. Proposed System: Savegame and State Serialization Requirements

## Purpose

Ensure proposed systems can persist deterministically.

## Required Persistent State

- Scheduler arrays, current tick, active schedulables, and deterministic tie-breaker sequence.
- Pending player intent / automation policy if saving during travel, rest, observe, or fast-forward.
- Event queues or replay-relevant event batches.
- Dirty state only if required for exact mid-frame restoration; otherwise it may be reconstructed from authoritative state.
- Runtime mode if saving mid-flow.
- Animation state only when mid-animation saves are supported.
- Roster, roles, bonds, mental state, availability.
- BaseCamp resource state and facilities.
- Active assignments and projects.
- Archive fragments, Concepts, research projects.
- Road graph, road segment state, Waystations.
- Overland scent fields or summaries.
- Predator state and territories.
- Wildness/phase region state.
- Ghost Term load.
- Cave survey and stratigraphy records.
- Map planes: terrain, features, walkability, transparency/opacity, movement cost, height, ceiling, terrain flags, and scene geometry version.
- Knowledge/memory planes: known, currently visible, remembered terrain/features, last seen tick, memory intensity, and memory flags.
- Light source table and gameplay-relevant light state.
- Site history knowledge and reveal flags.
- Practical magical tool state.
- RNG state.

## Existing System Integration

- `utils/savegame.py` or savegame-equivalent persistence.
- `utils.game_rng.GameRNG` state save/load.
- EntityRegistry serialization.
- Dense arrays serialized compactly.
- Polars tables serialized with IPC/Arrow where appropriate.

## Minimum Viable Version

- Serialize components and global records to a deterministic save payload.
- Reload and reproduce daily/system outcomes from same state.

---

# 25. Proposed System Priority

Recommended implementation order:

## Phase 1: Leadership Core

1. Expedition roster generation.
2. Couples Draft.
3. Basic assignments.
4. BaseCamp resource state.
5. Simple morale state.
6. Simple field party availability.

## Phase 1.5: Runtime Spine

1. `EventBatch`.
2. `TurnResult`.
3. Dirty changed-cell / changed-entity arrays.
4. Initial timed/environmental scheduler.

## Phase 2: Walkable Harbor and Archive Shell

1. Ruined harbor base map.
2. Physical BaseCamp entity.
3. Archive facility.
4. KnowledgeFragment pickup/deposit.
5. First Eureka recipe.
6. First practical magical tool.
7. `ViewportRenderInput` adapter for current renderer.
8. Camp lighting and memory overlay through draw-ready viewport arrays.

## Phase 3: Roads and Local Survey

1. Local resource survey.
2. First Ancient Road.
3. Road clearing.
4. First Waystation.
5. Route travel modifiers.
6. Map knowledge.
7. Travel policy over scheduler stepping.
8. Dirty movement-cost / scent / visibility updates for changed route cells.

## Phase 4: Scent Threats and Consequences

1. Base scent source.
2. Waystation scent source.
3. One apex predator.
4. Tracks/warnings.
5. Scent masking action.
6. Threat-to-camp event.
7. Sparse AI perception facts generated from dense scent/noise fields.
8. Event-importance interruption for travel, rest, and fast-forward.

## Phase 5: Caves and Knowledge Depth

1. Cave survey.
2. Cave categories.
3. Light/sound/scent cave play.
4. Stratigraphy tags.
5. Deep-time KnowledgeFragments.
6. Petra-like cave settlement prototype.
7. Layered opacity for smoke, mist, shafts, glass, foliage, and partial barriers.
8. Side-aware lighting and memory tinting for cave readability.
9. Channel-filtered perception for sound/scent/magic-sight experiments.

## Phase 6: Magic Cosmology

1. Wildness region tags.
2. Hybridization recipes.
3. Ghost Term hidden counter.
4. Archive reveals Ghost Term.
5. Doom Engine Gradient clue chain.
6. Persistent scar rules.
7. Magic-channel opacity and simulation-light separation.
8. Replay/debug traces from scheduler state and event batches.

## Phase 7: Continuous Presentation

1. Movement animation table.
2. Transient flare table.
3. UI overlay buffers.
4. Temporal cell transitions.
5. Fast-forward animation coalescing.

---

# 26. Implementation Guardrails

## 26.1 Do Not Duplicate Existing Ownership

- New production AI goes under `game/ai/`, not top-level `ai/`.
- `auto/` may be used for tuning, not production runtime.
- Sound/scent propagation concepts should extend or reuse `pathfinding/perception_systems.py`.
- Production FOV/LOS/light calls should use `game/world/` and `engine/render_lighting.py`.
- Runtime logic should not live in renderer code.
- Renderer code should consume composed viewport arrays, not own gameplay rules.
- Deterministic randomness must use `utils.game_rng.GameRNG`.

## 26.2 Keep Systems Independently Useful

Each proposed system should be playable in a minimal form.

Examples:

- Central Archive works with exact recipe tags before complex inference exists.
- Infrastructure works with one road before full road graph exists.
- Morale works with spouse grief before full social simulation exists.
- Wildness works with region tags before dense gradient fields exist.
- Scent threats work with one predator before ecology simulation exists.
- Cave survey works with tags before procedural archaeology exists.

## 26.3 Avoid Backend-First Design

Do not build a massive simulation before there is a player decision.

Every system needs:

1. A player decision.
2. A visible consequence.
3. A deterministic fallback.
4. A current repo integration point.

## 26.4 Preserve One Simulation Path

Do not create separate logic for manual turns, realtime display, travel, rest,
observation, and fast-forward.

These modes should differ only in scheduler policy, step budget, rendering cadence,
and interruption thresholds.

## 26.5 Preserve Presentation / Simulation Separation

Presentation can interpolate, fade, flash, tint, and animate.

Presentation must not mutate authoritative gameplay state unless it emits or
promotes a simulation event that is resolved by normal game systems.

---

# 27. Summary Matrix

| Proposed System | Primary New Module | Existing Integration Points | Player-Facing Purpose |
| --- | --- | --- | --- |
| Turn-Authoritative Runtime / Visual Composition | `game/runtime/scheduler.py`, `game/runtime/events.py`, `engine/visual_composer.py` | `game/world`, `engine`, `game/ai`, `pathfinding`, `utils.game_rng` | Manual turns, travel, rest, fast-forward, rich lighting, memory, and perception through one deterministic path |
| Expedition Roster / Couples Draft | `game/expedition/couples_draft.py` | `game/entities`, `utils.game_rng`, `game/ai` | Choose expedition strengths and failure modes |
| Assignment System | `game/systems/expedition_assignment_system.py` | `game_state`, `entities`, `ai_system` | Leadership opportunity cost |
| Base Camp Consequence Engine | `game/systems/base_camp_system.py` | `game/world`, `engine`, `entities` | Physical settlement change |
| Central Archive / Eureka | `game/systems/research_system.py` | `entities`, `game_state`, `magic`, `data` | Knowledge as loot |
| Infrastructure / Roads / Waystations | `game/systems/infrastructure_system.py` | `worldgen`, `game/world`, `pathfinding` | Surface campaign logistics |
| Overland Scent Threats | `game/systems/overland_threat_system.py` | `pathfinding`, `game/ai`, `game/world` | Legible predator pressure |
| Social Morale / Bonds | `game/systems/morale_system.py` | `death_system`, `entities`, `game/ai` | Social consequence |
| Morale-Aware GOAP | `game/ai/morale_adapter.py` | `game/ai/goap`, `ai_system`, `auto` as harness | Grief/refusal/labor behavior |
| Wildness Gradient | `game/systems/wildness_gradient.py` | `worldgen`, `magic`, `game/world` | Doom Engine pressure |
| Magic Hybridization | `magic/hybridization.py` | `research_system`, `effects`, `wildness_gradient` | Cultural magic synthesis |
| Ghost Term | `game/systems/ghost_term_system.py` | `magic`, `effects`, `research` | Hidden cost of ordered magic |
| Practical Magic Tools | `game/magic/practical_tools.py` | `items`, `magic`, `effects`, `engine` | Field-use magic |
| Cave Survey / Stratigraphy | `game/systems/cave_survey_system.py` | `Dungeon`, `game/world`, `research` | Caves as archives |
| Persistent Scars / Anomalies | `game/systems/anomaly_system.py` | `worldgen`, `Dungeon`, `magic`, `movement` | Learnable weirdness |
| Site History | `worldgen/site_history.py` | `Dungeon`, `research`, `campaign` | Layered human past |
| Reveal Ladder | `game/campaign/reveal_ladder.py` | `research`, `infrastructure`, `game_state` | Discovery-driven progression |
| Companion Expertise | `game/expedition/expertise.py` | `entities`, `research`, `survey`, `skills` | Companions matter |
| Expedition Knowledge / Map Memory | `game/knowledge/expedition_memory.py` | `game/world/memory`, `research`, `engine` | Separate world truth from known truth |
| Local Resource Survey | `game/systems/local_survey_system.py` | `worldgen`, `game/world`, `assignment` | Surface exploration before caves |
| Save/Load Extensions | `utils/savegame.py` extensions | `GameRNG`, `entities`, arrays, Polars | Deterministic persistence |

---

# 28. Closing Design Statement

The software architecture should make the Lost Continent Expedition vision executable without losing the strengths of the current Simple RL codebase.

The project should not become a disconnected pile of systems.

Every new system should reinforce the same core loop:

1. The player leads a small expedition.
2. The expedition survives from a ruined harbor base.
3. Roads and Waystations extend reach.
4. Field missions produce evidence.
5. Evidence returns to the Central Archive.
6. Archive synthesis unlocks new understanding and options.
7. Social, logistical, magical, and ecological consequences push back.
8. Caves and ruins reveal layered human history.
9. The Doom Engine Gradient and Ghost Term reveal that magic is moving from rigid order into wildness.
10. The player decides what to risk, what to preserve, what to exploit, and what to tell the east.

The implementation should remain deterministic, data-driven, modular, and
performance-conscious.

The runtime should be energy-scheduled in simulation, array-backed in state,
event-batched in communication, policy-driven in flow, deterministic in replay,
layered in visibility and perception, incremental in lighting, memory-driven in
rendering, and continuous only in presentation.

The player-facing goal is responsibility under uncertainty.

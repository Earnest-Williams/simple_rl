# Lost Continent Expedition Roguelike

## Cohesive North Star, Systems Vision, and Future Design Spine

**Working title:** Lost Continent Expedition Roguelike

**Possible subtitle:** A leadership-driven expedition roguelike about rebuilding a foothold on a lost continent, following ancient roads into cave-cities and deep human history, and discovering that the calamity which emptied the west was only the first visible fracture in a cosmic cycle carrying magic from rigid order into wildness.

---

## Document Status

This document merges the two uploaded Lost Continent Expedition drafts into a single cohesive version.

It is not a sprint specification, data schema, content bible, or implementation checklist. It is the high-level creative, systemic, and architectural North Star for the game. It also intentionally folds in the future-facing systems cluster that was previously marked as unsupported in the current codebase: infrastructure systems, morale and social-bond cascades, the Central Archive and KnowledgeFragment research loop, Ancient Roads and Waystations, overland scent-gradient threat pressure, and the Doom Engine / wildness-gradient model.

Those systems should now be treated as **design intent**, not as claims about what the current repository already implements.

The repository already has strong technical foundations for this direction: a simulation-heavy roguelike/RPG orientation; deterministic RNG; procedural cave generation; integrated game, rendering, combat, AI, FOV, lighting, effects, entity, perception, and world systems; GOAP experimentation; sound/scent perception work; and a performance-oriented Python architecture. This document describes what those foundations are trying to become as a game.

It answers:

> What is the game trying to become?

It does not answer:

> What exact formulas, widgets, class layouts, map schemas, and content tables do we implement this sprint?

Those come later.

---

# 1. One-Sentence Vision

A leadership-driven expedition roguelike about rebuilding a foothold on a lost continent, following ancient roads into abandoned settlements and cave-cities, and uncovering a deep human past that reveals magic itself is entering a dangerous transition from rigid order into wildness.

---

# 2. The Core Fantasy

The player is the leader and financier of a rediscovery expedition to a western continent that has been lost for a thousand years or more after a vast calamity.

He bankrolled the mission.

He commands it.

He makes the decisions.

The expedition ship crosses the sea, lands at a natural harbor where a dead port city once stood, unloads equipment, supplies, and twenty-four people, then leaves. Most of the people who came on the voyage were sailors, crew, transport hands, or temporary labor. They do not remain.

The people left behind are the expedition.

The player is one of them, but not merely one of them. He is responsible for them.

He decides who repairs buildings, who hunts, who scouts, who studies inscriptions, who guards the base, who clears the ancient road, who rests, who risks the ruins, who descends into caves, and who stays behind.

If he takes someone into the field, that person is not working at base.

That is one of the core pressures of the game.

The player is not a wandering adventurer who happens to find a town. He is the person who must keep the town alive while deciding how much risk the mission can bear.

The game should repeatedly make the player think:

> “I need the mason with me to inspect that carved cliff settlement, but if I take him, the storehouse roof slips another day.”

> “I need the hunter to track the game trail inland, but the camp needs meat.”

> “I need the scholar to read the cave inscription, but someone needs to catalog the previous expedition’s journals.”

> “I need the hidden-light lantern in the field, but if I take it, the night watch loses the safest light.”

> “I need the bonded couple’s combined skill set, but if one dies, the survivor may not recover before winter.”

The player’s authority should feel useful, costly, and lonely.

---

# 3. Genre Identity

The game is a hybrid of:

- Expedition leadership game.
- Simulation-heavy roguelike.
- Lost-continent exploration.
- Archaeological mystery.
- Settlement consequence engine.
- Practical-magic survival game.
- Cave and ruin exploration.
- Deep-time historical reveal.
- Social-roster pressure game.
- Cosmic magical phase-transition story.

It is not a generic dungeon crawler.

It is not a pure colony sim.

It is not a high-magic combat RPG.

It is not a cinematic, linear adventure.

It is not a survival crafting game where the fantasy is personally gathering hundreds of sticks.

It is not a technology demo where advanced simulation matters more than player-facing drama.

It can borrow from Caves of Qud, TOME, Angband, Journey to the Center of the Earth, Allan Quatermain, The Hobbit and The Lord of the Rings, Bone Tomahawk, The Descent, Uncharted, Around the World in 80 Days, The Lost World, Dwemer ruins, Morrowind, Petra, Rising Star Cave, Panga ya Saidi, Border Cave, and deep archaeological discovery.

But the finished identity should be its own:

> A procedural magical expedition simulator about leadership, lost history, practical magic, and a continent scarred by a reality break.

---

# 4. Current Technical Foundation and Design Intent

The current repository should be understood as the technical seedbed, not yet the finished game identity.

Existing or documented foundations include:

- A main game engine under `game/` integrating entities, effects, combat, movement, equipment, AI, world state, and turn processing.
- An `engine/` rendering and lighting layer with FOV, light-aware rendering, memory behavior, entity rendering, and window management.
- A canonical `Dungeon/` cave-generation pipeline preserving depth, height, chamber, material, vertical connectivity, and grid data through a 3D-to-2D shaping process.
- `pathfinding/` sound and scent perception concepts, with production-facing perception integration under game AI and world systems.
- `utils.game_rng.GameRNG` as the canonical deterministic randomness abstraction.
- GOAP experimentation under `auto/`, with production GOAP behavior integrated through `game/ai/`.
- Top-level `ai/` as an R&D space for community AI concepts.
- A bifurcated skill-system architecture: game-facing runtime hooks under `game/skills/`, and reusable or research-oriented skill rules under top-level `skills/`.
- Magic and scripting foundations through `magic/` and scripting/effect work.
- A documented engineering culture emphasizing Python 3.11+, strict typing, Polars, NumPy, Numba, deterministic simulation, explicit data flow, and performance-conscious design.

This document’s future systems should be developed as extensions of those foundations, not as disconnected feature wishes.

The key technical direction is:

> Build a deterministic, data-driven expedition simulator where the player-facing fantasy is leadership, consequence, discovery, and practical magic, while the backend remains modular enough to support deeper simulation over time.

---

# 5. The Two-Tier Ambition Model

The project should have two explicit ambition tiers:

1. **True Targets**
2. **Moonshots**

This distinction is essential.

The project is technically ambitious. It uses or contemplates high-performance simulation techniques: Polars, NumPy, Numba, SciPy, deterministic RNG, flow fields, columnar data layouts, sparse updates, and potentially future GPU acceleration.

That opens the door to fascinating possibilities: continent-scale simulation fields, flowing gases, water, scent, souls, herds, magical pressure, Ghost Term accumulation, predator migration, and thousands of animals moving across a living landscape.

Those are worth designing toward.

But the game must not depend on them.

## 5.1 True Targets

True Targets are the game’s real commitments.

They are ambitious, but they must be achievable without relying on speculative GPU systems or massive simulation scale.

If all moonshots fail, the True Targets should still produce an excellent game.

True Targets guide:

- Core mechanics.
- UI.
- Writing.
- Content.
- Architecture.
- Pacing.
- Playable milestones.
- Player-facing systems.

## 5.2 Moonshots

Moonshots are extraordinary possibilities.

They are research targets, architectural inspirations, and long-term expansions. They may influence data layout and system boundaries, but they must not block the core game.

Every moonshot should have three versions:

1. **Narrative version** — represented through authored or procedural events.
2. **Approximate simulation version** — represented through coarse grids, tags, counters, local fields, sparse updates, or regional summaries.
3. **Full simulation version** — implemented only if the technology, performance, and development time justify it.

The rule:

> Moonshots may expand the simulation, but the game must remain compelling if every moonshot is replaced by a simpler, deterministic, CPU-friendly approximation.

---

# 6. The World Premise

A thousand years ago, or perhaps longer depending on the final timeline, a great calamity struck the western continent.

The peoples of that continent fled east across the sea. Most died during the crossing. It was not a good season for sailing. Those who survived carried oral histories of a dead homeland, cave refuges, old port cities, ancient paths, and people who had once lived in caves before the calamity.

Over generations, memory degraded into myth, doctrine, politics, taboo, and simplified school history.

The west became “lost.”

Now, after centuries of fear, curiosity, and renewed ambition, rediscovery missions are sent west.

The player’s expedition is one of them.

No one knows what happened to earlier attempts. Officially, perhaps none are known. Unofficially, there are rumors. The player may suspect the crown, academy, merchants, church, or private financiers know more than they admit.

The expedition lands at a natural harbor where a port city once stood.

Stone buildings still exist. Many have tumbled down. Most non-stone buildings have vanished almost completely. Streets are buried under soil and brush. Roofs are gone. Cellars remain. Cisterns may remain. River channels may remain. Road gates, shrines, quays, walls, sea stairs, storage houses, civic buildings, and stone foundations remain.

There are signs that people lived here after the calamity.

There are signs that previous expeditions reached this place.

Some signs may be a decade old.

Some may be older.

Some may be impossible to date.

The ship unloads the expedition’s equipment and supplies, then leaves.

Twenty-four people remain.

Twelve men. Twelve women.

The expedition must survive, build, scout, interpret, and decide how far to go.

---

# 7. The Player Role

The player is the expedition leader.

He could be a man or a woman, but the working assumption is “our man,” the patron-leader who financed the mission and has formal authority over it.

His role combines:

- Patron.
- Commander.
- Explorer.
- Surveyor.
- Decision-maker.
- Judge of risk.
- Keeper of morale.
- Interpreter of incomplete evidence.
- Final authority when plans fail.

He is not necessarily the strongest fighter, best scholar, most skilled mage, or most practical laborer.

His power is command.

His vulnerability is responsibility.

## 7.1 Leadership as Gameplay

Every day, the player decides what the expedition does.

Core work streams:

- Food.
- Water.
- Shelter.
- Health.
- Security.
- Morale.
- Research.
- Construction.
- Tool repair.
- Magical preparation.
- Path-clearing.
- Mapping.
- Field scouting.
- Ruin exploration.
- Cave survey.
- Rest and recovery.

Every person assigned to one stream is absent from another.

Every tool taken into the field is unavailable at base.

Every day spent exploring is a day the base may stagnate.

Every day spent consolidating the base is a day the mysteries remain unresolved.

The player is always trading safety, knowledge, time, and capability.

## 7.2 The Leader Must Sometimes Go Personally

The protagonist should not be forced into every minor task, but there should be strong reasons he personally leads important field missions:

- His authority may be needed for dangerous decisions.
- His expeditionary tools may be bound to him.
- His judgment may be required when evidence is ambiguous.
- Companions may refuse certain missions unless he leads.
- Certain discoveries may be politically or spiritually sensitive.
- Some magical tools may respond only to their owner or patron.
- The player must personally witness key reveals.

This preserves roguelike field play while respecting the command fantasy.

---

# 8. The Expedition Roster and Couples Draft

The twenty-four people are not generic workers.

They are the soul of the game.

The roster is small enough for the player to know them and large enough that assignment tradeoffs matter.

## 8.1 Drafting the Roster

At New Game, the player does not draft isolated individuals. He drafts interlocking family units, usually couples, with complementary or risky skill packages.

Examples:

- Mr. Grain Farmer Brown and Mrs. Baker Brown.
- A scholar married to an archivist.
- A mason married to a healer.
- A hunter married to a cartographer.
- A practical mage married to a skeptical surveyor.
- A carpenter married to a rope worker.
- A guard married to a cook.
- A naturalist married to a charcoal burner.

This lets the player choose a failure state.

A roster of brilliant academics may unlock rapid research and magical interpretation, but risk starvation.

A roster heavy with farmers, hunters, and laborers may survive well, but be slow to understand inscriptions, ruins, and deep-time evidence.

A roster with strong guards may handle field danger, but lag in road repair, healing, and research.

The draft should make the player feel the expedition’s shape before the first turn begins.

## 8.2 Character Data

Each character should have:

- Name.
- Sex.
- Age band.
- Primary skill.
- Secondary skill.
- Base function.
- Field function.
- Temperament.
- Health.
- Morale and trust.
- One fear.
- One ambition.
- One reason they joined.
- One practical limitation.
- Social bonds to their drafted partner.
- Possible secondary relationships with others.

Possible expedition roles:

- Mason.
- Carpenter.
- Hunter.
- Herbalist.
- Scholar.
- Surveyor.
- Guard.
- Cook.
- Sailor.
- Smith or tinker.
- Farmer.
- Healer.
- Animal handler.
- Charcoal burner or pitch worker.
- Scribe or accountant.
- Practical mage or inscription specialist.
- Rope worker.
- Fisher.
- Scout.
- Laborer with high endurance.
- Priest or ritualist.
- Naturalist.
- Cartographer.
- Toolmaker.
- Archivist.
- Roadwright.
- Stonecutter.
- Linguist.
- Caver.

These are not RPG classes. They are expeditionary capabilities.

## 8.3 Social Consequence

Losing a person mechanically and socially changes the base.

Losing the only mason is not just sad. It changes which ruins can be stabilized, which roads can be repaired, which cave thresholds can be opened safely, and how quickly the base improves.

Losing a bonded partner creates a second-order crisis. The surviving partner’s morale may shatter. Their GOAP priorities may change. They may abandon their farming duties to grieve, wander, refuse orders, take risks, lash out, or demand burial rites.

That can cascade into economic failure.

The key design rule:

> A death is not just a removed unit. It is a change in the expedition’s social machine.

---

# 9. Campaign Shape: Rings of Discovery

The campaign unfolds through rings of discovery.

## 9.1 Ring One: The Harbor City

The game begins at the dead port.

Initial threats are practical:

- Shelter.
- Water.
- Food.
- Weather.
- Security.
- Morale.
- Disease.
- Injury.
- Unknown terrain.

Initial mysteries are quiet:

- Soot in a fireplace that is too recent.
- A wall repaired long after the city fell.
- A foreign tool mark.
- A broken eastern crate.
- A rusted buckle from a prior expedition.
- A cellar used as shelter.
- A symbol scratched into a doorway.
- A road marker pointing inland.
- A shrine inscription that differs from oral history.

The port teaches the player that the west is not untouched and not simple.

## 9.2 Ring Two: The Surface Campaign and Local Survey

Before chasing caves, the expedition must understand its immediate surroundings.

The world does not scale with the player. A primeval forest might contain nothing but lethal apex predators and zero treasure. The correct decision may be to mark the boundary, retreat, and come back with better preparation.

The player must physically walk and survey the terrain to secure:

- Fresh water.
- Good soil.
- Food sources.
- Timber.
- Pitch or resin.
- Clay.
- Lime.
- Stone.
- Reeds.
- Salt.
- Medicinal plants.
- Game trails.
- Fishing areas.
- Safe paths.
- Dangerous plants.
- Predator territories.
- Weather exposure.
- Possible disease sources.

Procedural generation should vary the exact problem.

Maybe the town has a river. Maybe the river shifted. Maybe the cisterns work but are contaminated. Maybe water is easy but timber is far away. Maybe prey is abundant but predators follow the same trails.

## 9.3 Ring Three: The Ancient Path

At least one ancient path leads away from the town.

Finding it is a major milestone.

Opening it is not a one-day event. It is a campaign project.

The road may be buried, overgrown, broken, flooded, watched by animals, collapsed in places, or interrupted by ruined culverts and bridges.

The expedition must:

- Locate the roadbed.
- Clear brush.
- Repair sections.
- Mark safe routes.
- Secure dangerous stretches.
- Establish Waystations.
- Decide how much labor to allocate.
- Decide whether to push forward or consolidate.
- Deal with branches and false leads.

The ancient path is not just a route. It is proof that the landscape was organized by human life.

It can lead to:

- Farming settlements.
- Shrines.
- Watch posts.
- Quarries.
- Burial grounds.
- Cliff settlements.
- Waterworks.
- Road forks.
- Cave entrances.
- Previous expedition camps.
- Places where the road behaves strangely due to the calamity.

## 9.4 Ring Four: Inland Settlements and Data Extraction Raids

Before the caves dominate play, the player should find settlements.

These settlements reveal staged collapse, survival, adaptation, and ambiguity.

Possible discoveries:

- A village abandoned before the exodus.
- A hamlet used as a refugee gathering point.
- A settlement occupied after the calamity.
- A place where prior expeditions camped.
- A settlement with eastern repairs.
- A settlement with altered human remains.
- A settlement with stable wild scars.
- A place deliberately erased or sealed.
- A place where the road splits toward caves.
- A ruin currently held by hostile remnants or post-calamity factions.

This stage makes the central question more complicated:

> Did people survive?

The objective is rarely to “clear the dungeon.” The objective is to extract data, identify risks, recover evidence, rescue knowledge, and decide whether contact, evasion, theft, negotiation, or violence is worth the cost.

A ruin held by dangerous inhabitants may still contain vital anthropological evidence. The player weighs the inhabitants’ knowledge against the blood cost of extracting it.

## 9.5 Ring Five: The First Caves

The first caves may be ordinary.

Some should be boring.

That matters.

Not every cave is a dungeon. Some are:

- Wet holes.
- Animal dens.
- Storage caves.
- Burial caves.
- Shallow shelters.
- Water caves.
- Guano caves.
- Collapsed passages.
- Empty limestone systems.
- Caves with only one sign of human use.
- Caves with a deep shaft that cannot yet be descended.

A boring cave can still matter because it provides:

- Water.
- Shelter.
- Fertilizer.
- Cold storage.
- A shortcut.
- Animal evidence.
- Airflow hints.
- Route options.
- One historical clue.
- A reason to return later.

The player should not know whether a cave is important without surveying it.

## 9.6 Ring Six: Petra-Like Cave Settlements

Eventually, the expedition finds caves that are not merely caves.

They are carved.

They contain:

- Facades cut into stone.
- Terraced dwellings.
- Cisterns.
- Door sockets.
- Stairways.
- Tombs.
- Assembly halls.
- Storage niches.
- Light wells.
- Acoustic chambers.
- Ritual shafts.
- Smoke-blackened ceilings.
- Emergency refuge modifications.
- Older habitation layers.

This confirms part of the oral history: people did flee into caves.

It also complicates it: the caves were inhabited before the calamity.

The cave systems were not merely hiding places. They were homes, cities, sanctuaries, archives, and magical instruments.

## 9.7 Ring Seven: Deep-Time Archaeology

The deepest reveal is not simply “there were cave people.”

It is:

> There were people here far earlier than the east believes, and they were far more sophisticated than expected.

Inspired by Rising Star Cave, Panga ya Saidi, Border Cave, and deep archaeological sites, the player should find evidence of:

- Very old hearths.
- Pigment processing.
- Burials.
- Symbolic marking.
- Beads.
- Engraved stones.
- Tool traditions.
- Food remains.
- Seasonal occupation.
- Water management.
- Acoustic ritual spaces.
- Route systems.
- Deep cave familiarity.
- Magic integrated with breath, darkness, stone, memory, and sound.

This should overturn assumptions.

The ancient cave peoples were not primitive. They understood parts of the world that ordered eastern civilization forgot or never knew.

---

# 10. The Walkable Consequence Engine

The settlement is not a menu.

It is a physical, walkable space on the map.

The base is where resources, people, tools, discoveries, grief, trust, fear, and research physically accumulate.

The design goal:

> Consequences should be visible, walkable, interruptible, and spatial.

## 10.1 Morning Council

Each day begins with review:

- Food.
- Water.
- Shelter.
- Health.
- Morale.
- Security.
- Current projects.
- Weather.
- Injuries.
- Discoveries.
- Warnings.
- Available tools.
- Companion status.
- Active routes.
- Known threats.
- Prior expedition clues.

Then the player assigns people to work.

## 10.2 Assignment and Delegation

Possible assignments:

- Repair shelter.
- Guard base.
- Hunt.
- Fish.
- Forage.
- Scout.
- Clear road.
- Study inscriptions.
- Catalog artifacts.
- Treat sick or injured.
- Prepare tools.
- Maintain magical equipment.
- Build storage.
- Watch animals.
- Survey water.
- Rest.
- Join field party.
- Maintain Waystation.
- Stabilize road section.
- Work in Central Archive.
- Process KnowledgeFragments.
- Conduct controlled magical experiment.

The player chooses companions and tools for any personal expedition.

## 10.3 Field Expedition

Field play is the roguelike layer.

The player moves through:

- Ruined city.
- Brush.
- Roads.
- Settlements.
- Shrines.
- Quarries.
- Rivers.
- Watch posts.
- Caves.
- Cave settlements.
- Deep systems.
- Anomaly zones.

Field play includes:

- Navigation.
- Investigation.
- Light management.
- Sound management.
- Scent and tracking.
- Combat when necessary.
- Stealth.
- Tool use.
- Companion skills.
- Resource use.
- Route marking.
- Risk assessment.
- Returning before disaster.

## 10.4 Return, Report, and Deposition

When the player returns, discoveries do not automatically become global knowledge.

They must be physically deposited, cataloged, interpreted, or demonstrated.

The player returns to base and chooses what happens to evidence:

- Store an artifact.
- Give a journal to the archivist.
- Ask a scholar to translate markings.
- Hand a tool to a craftsperson.
- Bring a witness to a disputed clue.
- Reconstruct a route on the map table.
- Compare a ruin symbol against an earlier cave mark.
- Test a material under a hidden-light lantern.
- Place a KnowledgeFragment into the Central Archive.

This is where the Central Archive becomes the knowledge economy.

## 10.5 Night Events

At night:

- Weather shifts.
- People argue.
- Someone gets sick.
- A guard reports lights inland.
- Animals approach.
- A tool behaves oddly.
- A prior expedition object is discovered in storage.
- A companion has a dream.
- A perimeter mark is disturbed.
- Morale rises or falls.
- Trust changes.
- A hidden trait or fear emerges.
- A grieving partner fails to report for duty.
- A Waystation signal is overdue.
- A scent trail reaches camp.

---

# 11. Knowledge as Loot and the Central Archive

The most important loot is knowledge.

The player gains power by learning.

Knowledge can reveal:

- A safe water source.
- A dangerous plant.
- A viable timber source.
- A repairable building.
- A road branch.
- A cave entrance.
- A route through a cave.
- A symbol’s meaning.
- A prior expedition’s path.
- A settlement’s history.
- A magical tool’s provenance.
- A survivor custom’s purpose.
- A way to stabilize an anomaly.
- A warning sign.
- A phase-cycle clue.

Knowledge should unlock:

- Base projects.
- Safer routes.
- Better assignments.
- Companion dialogue.
- Research options.
- Magical repairs.
- Field procedures.
- Settlement improvements.
- New expeditions.
- Strategic decisions.
- Hybrid tools.
- Concept abilities.

## 11.1 KnowledgeFragments

A KnowledgeFragment is a discrete piece of recoverable, depositional information.

Examples:

- Partial inscription.
- Tool mark rubbing.
- Artifact mechanism sketch.
- Survivor phrase.
- Cave acoustic observation.
- Burial-position note.
- Prior expedition journal entry.
- Road marker geometry.
- Weird-light behavior.
- Broken tool performance test.
- Material sample.
- Local custom.
- Stable anomaly measurement.
- Scent-pattern observation.
- Route diagram.
- Myth fragment.

Fragments have value alone, but greater value in combination.

## 11.2 The Central Archive

The Central Archive is a base-camp facility and play loop.

It is not just an inventory screen.

It is the physical place where evidence becomes expedition power.

Archive work includes:

- Cataloging.
- Cross-referencing.
- Translation.
- Replication.
- Controlled experiment.
- Material comparison.
- Route reconstruction.
- Prior expedition analysis.
- Magical interface comparison.
- Cultural practice comparison.
- Risk assessment.
- Concept synthesis.

The Archive requires people, time, tools, safety, morale, and light.

If the player takes the scholar into the field, the Archive slows.

If the archivist’s spouse dies, the Archive may halt.

If the hidden-light lantern goes into the field, the Archive cannot perform certain observations.

If a road is blocked, the Archive lacks fresh field evidence.

## 11.3 Eureka Moments

When the right KnowledgeFragments are deposited and processed, the expedition can synthesize new Concepts.

A Concept is a learned, actionable abstraction.

Examples:

- “This road system encodes water access.”
- “This cave mark is not writing; it is sung notation.”
- “Broken inscription strokes can widen tolerance near the west.”
- “Certain thresholds reject exact eastern formula but accept breath timing.”
- “This settlement survived after the supposed end.”
- “The same symbol appears in road markers and burial chambers.”
- “A Waystation placed at a road fork reduces travel loss.”
- “Predators are following our supply scent, not random patrols.”
- “The hidden-light lantern isolates the bearer because it masks shared perception.”

Concepts unlock:

- New base projects.
- New field procedures.
- Safer interpretations.
- Hybrid tools.
- Repair options.
- Road-clearing efficiency.
- Cave-survey methods.
- New route confidence.
- Cultural-magic translation.
- Companion assignments.
- Strategic warnings.

The research loop is:

> Field evidence → KnowledgeFragment → Central Archive deposition → synthesis → Eureka → new option in the world.

---

# 12. Roads, Infrastructure, and Waystations

Roads are not background terrain.

They are the expedition’s arteries.

The ancient road network proves that the continent was not empty wilderness. It was organized, inhabited, maintained, and meaningful.

## 12.1 Ancient Roads

Roads should support:

- Movement.
- Supply.
- Signage.
- Historical inference.
- Route planning.
- Predator tracking.
- Waystation placement.
- Social risk.
- Magical anomalies.
- Discovery pacing.

They may be:

- Buried.
- Overgrown.
- Flooded.
- Broken.
- Collapsed.
- Blocked by fallen masonry.
- Washed out.
- Obscured by brush.
- Claimed by animals.
- Watched by hostile survivors.
- Spatially scarred.
- Shorter or longer under certain conditions.

## 12.2 Road Work as Campaign Project

The player can assign labor to:

- Clear brush.
- Rebuild culverts.
- Raise markers.
- Repair bridges.
- Secure dangerous stretches.
- Install rope guides.
- Establish water points.
- Build shelters.
- Survey forks.
- Mark safe passage.
- Remove blockages.
- Ward or disguise vulnerable sections.

This is not a crafting grind. It is strategic labor allocation.

The question is:

> How much of today’s expedition capacity is spent making tomorrow’s route safer?

## 12.3 Waystations

Waystations extend logistical reach.

They are physical, vulnerable, useful places.

A Waystation may include:

- Shelter.
- Water cache.
- Food cache.
- Signal marker.
- Scent mask.
- Tool chest.
- Repair materials.
- Rope and route markers.
- Emergency lantern.
- Medical kit.
- Small shrine or morale object.
- Road map copy.
- Predator warning marker.
- Archive drop box for field notes.

Waystations create new opportunities and new liabilities.

They let the expedition push further inland, but they also generate scent, require maintenance, and become targets.

A broken Waystation can strand a field party.

A well-placed Waystation can transform a road branch from impossible to practical.

## 12.4 Infrastructure System Design Intent

A future infrastructure system should process:

- Road clear state.
- Road blockages.
- Bridge and culvert status.
- Waystation condition.
- Travel modifier components.
- Supply-route access.
- Predator scent pressure.
- Field-party return risk.
- Base-to-field logistics.
- Labor assignments.
- Tool availability.
- Weather damage.
- Morale impact from unsafe routes.

This system should not be a detached construction minigame. It should mutate the same world the player walks through.

---

# 13. Light, Sound, Scent, and Terrain

This should be one of the game’s signature systems.

The existing technical foundation around perception, FOV, lighting, sound/scent flow, and terrain should become a player-facing identity.

## 13.1 Light

Light should:

- Reveal.
- Expose.
- Comfort.
- Attract.
- Distort.
- Interact with magic.
- Define tactical space.
- Signal danger.
- Affect morale.
- Reveal inscriptions.
- Awaken things.
- Fail in bad air.
- Behave strangely near anomalies.

Examples:

- A normal lantern attracts animals and people.
- A hidden-light lantern illuminates only for the bearer but isolates companions.
- A fuel-less flame may be valuable but phase-sensitive.
- Some cave markings appear only under certain light.
- Some creatures hunt light.
- Some survivor customs forbid light in certain chambers for practical reasons.

## 13.2 Sound

Sound should:

- Travel through cave systems.
- Alert creatures.
- Reveal chamber size.
- Misdirect enemies.
- Expose hidden shafts.
- Interact with sung magic.
- Carry danger.
- Help map spaces.
- Activate old systems.

Examples:

- Throwing a stone lures a blind predator.
- A bell casts sound elsewhere.
- A cave song stabilizes a threshold.
- A gunshot saves the player but wakes deeper things.
- Certain chambers amplify whispers dangerously.
- Some roads are safer when walked silently.

## 13.3 Scent and the Hunt

Scent should:

- Create trails.
- Attract predators.
- Reveal recent passage.
- Linger in still air.
- Be masked by clay, smoke, herbs, water, or magic.
- Help animals and some altered people track.
- Behave differently in caves, roads, and airflow systems.

The base camp and active Waystations should generate scent pressure across the overland map.

Apex predators spawned in deep wilderness do not appear as random encounters. They follow scent gradients, food traces, noise, carcasses, or supply movement.

This creates emergent siege scenarios:

- A supply caravan’s scent trail is picked up.
- A Waystation attracts scavengers.
- A predator follows repeated road traffic.
- A hunting party draws something larger toward camp.
- Scent masking becomes strategic infrastructure, not flavor.

## 13.4 Terrain

Terrain should matter.

Not just walls and floors.

Important terrain:

- Ledges.
- Shafts.
- Cliffs.
- Slopes.
- Low ceilings.
- Crawlspaces.
- Wet stone.
- Unstable masonry.
- Flooded passages.
- Bad air pockets.
- Brush.
- Ancient roadbeds.
- Cisterns.
- Carved thresholds.
- Burial chambers.
- Resonant rooms.
- Spatial scars.

The player should often think:

> “Do I light the room, listen in the dark, send a sound elsewhere, mask our scent, tie a route cord, or turn back?”

---

# 14. The Settlement as Consequence Engine

The base is not a full city-builder, but it is not decorative.

It is the consequence engine.

It responds to:

- Player absences.
- Assignment choices.
- Food shortage.
- Water security.
- Repairs.
- Deaths.
- Injuries.
- Morale.
- Fear.
- Discoveries.
- Lies.
- Truth.
- Magical risks.
- Weather.
- Animal pressure.
- Prior expedition evidence.
- Contact with survivors.
- Phase anomalies.
- Road state.
- Waystation state.
- Social bonds.

Settlement state includes:

- Food.
- Water.
- Shelter.
- Health.
- Security.
- Morale.
- Trust in leader.
- Research.
- Construction.
- Tools.
- Magical assets.
- Route access.
- Stored artifacts.
- Injuries.
- Graves.
- Conflicts.
- Known risks.
- Archive progress.
- Waystation network.
- Predator pressure.

Discoveries change the settlement:

- A cistern map improves water security.
- A timber source speeds construction.
- A repaired storehouse reduces food spoilage.
- A previous expedition journal lowers morale but unlocks a route.
- A hidden-light lantern improves night watch unless taken into the field.
- A strange corpse creates fear, research, or taboo.
- A survivor custom improves cave safety but angers ordered traditionalists.
- A horned lineage discovery causes political conflict.
- A road shrine clue opens the path to a cave settlement.
- A spouse’s death halts labor and spreads fear.
- A Waystation failure blocks exploration and raises blame.

---

# 15. Social Morale, Bonds, and GOAP Priorities

The expedition is not just a list of workers.

It is a social system.

## 15.1 Bonded Couples

The Couples Draft means many roster members arrive with a primary social bond.

Bond consequences:

- Emotional resilience from being together.
- Higher morale when assigned compatible work.
- Panic when separated too long under stress.
- Grief when a partner dies.
- Refusal or desperation if a partner is missing.
- Conflicting needs when one partner is needed in the field and the other at base.

## 15.2 Morale as Behavior Input

Morale should not only be a number.

It should affect behavior.

Low morale may cause:

- Slower work.
- Refusal.
- Flight.
- Carelessness.
- Hoarding.
- Argument.
- Sabotage.
- Religious panic.
- Risky volunteering.
- Withdrawal.
- Grief loops.
- Abandonment of ordinary duties.
- Demand for burial, justice, or truth.

High morale may cause:

- Faster work.
- Volunteering.
- Better night watch.
- Recovery.
- Shared labor.
- Resilience after discovery.
- Trust in dangerous orders.

## 15.3 SocialBond Death Cascades

If a bonded partner dies in the field, the survivor should not merely receive a one-time debuff.

Their priorities change.

Examples:

- The farmer stops farming.
- The archivist refuses to catalog the artifact that caused the death.
- The hunter demands revenge.
- The healer overworks and collapses.
- The guard refuses to let the leader take anyone else.
- The scholar becomes obsessed with proving the death meant something.
- The surviving partner wanders to the grave at night.

This can cascade into base instability.

## 15.4 GOAP Reweighting

A future morale system should reweight action costs and goals for autonomous workers.

Example:

- A grieving farmer no longer treats “tend field” as cheap and obvious.
- “Visit grave” becomes high priority.
- “Argue with leader” becomes possible.
- “Refuse dangerous road assignment” becomes more likely.
- “Seek isolation” competes with base labor.
- “Protect surviving loved ones” overrides economic work.

This makes social state physically visible in the base.

The goal is not melodrama for its own sake. The goal is consequence.

---

# 16. Magic: Deterministic Law, Cultural Interface

Magic in this world is deterministic.

But people do not understand the underlying mechanism.

Each culture possesses partial, inherited, practical interfaces with magic. Cultures can reliably produce certain effects, but they often misunderstand which parts of their practice are essential.

Magic is not merely belief. It is not arbitrary.

It is law accessed through incomplete cultural technique.

## 16.1 Pattern Channels

A magical effect may depend on patterns across many channels:

- Body.
- Voice.
- Breath.
- Rhythm.
- Mental attention.
- Material.
- Inscription.
- Geometry.
- Tool construction.
- Timing.
- Place.
- Memory.
- Social ritual.
- Song.
- Gesture.
- Symbol.
- Direction.
- Light.
- Acoustics.

No culture fully understands all channels.

Each culture has discovered reliable bundles.

## 16.2 Eastern Inscription Magic

The protagonist’s culture uses inscriptions.

They are runic, not because reality intrinsically requires runes, but because this is the interface the east inherited and refined.

Another culture might use:

- Circles.
- Knots.
- Beads.
- Punctures.
- Woven patterns.
- Cut grooves.
- Color bands.
- Architectural ratios.
- Sung coordinates.
- Carved relief postures.

Eastern inscription magic is reliable in the ordered age.

But it is also narrow.

It is a survivor tradition, not the whole truth.

## 16.3 Cultural Translation Is Hard

A culture that knows how to make fire burn without fuel may not know how to teach another culture to do it.

A culture that knows how to make rope remember may not know how to translate that into inscription.

A sung tradition may not map into runes.

A geometric cave tradition may do things eastern notation cannot express.

This makes magical research archaeological and anthropological.

The player is not merely collecting spell scrolls. He is comparing damaged interfaces with a law no one fully understands.

## 16.4 Accidental Hybridization

Because the western continent is approaching a wildness transition, the tolerances of reality are widening.

The player’s ignorance of “how things are supposed to be done” can become an asset.

If he pays close attention, he can discover cross-pollinated practices:

- Eastern inscriptions activated by western breath timing.
- Song traditions stabilizing damaged runes.
- Gesture and carved geometry producing an effect neither culture would predict alone.
- Broken tools working better near certain sites.
- A route marker functioning as a magical diagram.
- A cave chamber acting as the missing component of an inscription.

Hybridization should feel like discovery, not spellcraft UI.

## 16.5 Player-Facing Magic

The player should mostly encounter magic through:

- Objects.
- Tools.
- Repairs.
- Materials.
- Inscriptions.
- Field procedures.
- Companion expertise.
- Research projects.
- Experiments.
- Cultural translation.
- Archaeological context.

The player should not generally be expected to write magical programs.

The scripting backend can exist for internal representation, authoring, and effects, but the core fantasy is not:

> Be a compiler engineer for magic.

The fantasy is:

> I am an expedition leader using inherited magical tools, foreign artifacts, scholars, craftspeople, and risky experiments to understand a lost continent.

## 16.6 Practical Magic

Magic should remain expeditionary and practical.

Examples:

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
- Oath-stone for short messages.

Combat magic may exist, but it is not the center.

No generic fireball spell list as the default design.

---

# 17. The Cosmic Pendulum, Ghost Term, and Doom Engine Gradient

Magic is not static.

The world moves through immense cycles between **Maximal Order** and **Maximal Wildness**.

This is the deeper cosmology of the setting.

## 17.1 The Hook

Magic is a cosmic pendulum swinging endlessly between rigid order and untamed wildness.

And the pendulum is slowing down.

In mythic dawn, a swing may have occurred within a single human lifetime.

Later swings took centuries.

Then millennia.

The current swing takes tens of thousands of years.

Civilizations experience only a tiny local segment of the curve and mistake it for permanence.

## 17.2 The Engine: Ghost Term

Magic is equation.

Every time a mage, tool, inscription, ritual, or magical engine casts a formulaic ordered effect, reality is forced to absorb an invisible mathematical deficit: the **Ghost Term**, the negative conjugate root of the spell.

The visible effect is only part of the event.

The hidden part is the deficit.

The Ghost Term prevents reality from finding a stable baseline. It accumulates, distributes, distorts, hides, or embeds itself in ways most cultures do not perceive.

Reality becomes an over-cranked spring.

As formulaic magic advances, civilizations gain:

- Precision.
- Repeatability.
- Industry.
- Infrastructure.
- Institutions.
- Magical engineering.
- Certification.
- Law.
- Hard science.
- Magical bureaucracy.

They believe they are mastering reality.

But they are also driving it toward Maximal Order.

At Maximal Order, magic becomes rigid, brittle, overdetermined, and dangerously intolerant.

Then the formulas break.

Causality slingshots past neutrality toward Wildness.

## 17.3 The Golden Ratio Cycle

The pendulum is governed by a growth pattern related to the Golden Ratio.

Each era expands.

The early world’s order/wild swings were short. People saw magic change within remembered time. Myths from that period are full of gods, monsters, living landscapes, impossible transformations, and miraculous figures.

Later eras lasted longer.

Today’s era is so vast that no civilization can see the curve from ordinary records.

An ordered civilization may have thousands of years of evidence that magic is and always has been a safe, predictable, hard science.

That evidence is real.

It is also local.

The civilization is standing on a vast curve and mistaking it for a straight line.

## 17.4 Ordered Side

On the ordered side, magic demands precision.

It favors:

- Exact inscription.
- Correct material.
- Strict geometry.
- Correct syllables.
- Formal gestures.
- Mental discipline.
- Repeatable tools.
- Schools.
- Institutions.
- Standard procedures.
- Industrial magic.
- Infrastructure.

Strength: reliability.

Failure mode: brittleness.

## 17.5 Transition Toward Wildness

As the pendulum moves away from Maximal Order, magical tolerances widen.

The required precision becomes fuzzier.

At first, this looks like decay:

- Formulas produce side effects.
- Inscriptions work when damaged.
- Improper rituals succeed.
- Foreign practices become easier to adapt.
- Tools exceed specifications.
- Untrained people cause minor effects.
- Ordered mages complain that magic is becoming impure.
- Institutions deny the pattern.

But this is not mere random chaos.

Reality is accepting approximation.

## 17.6 Deep Wildness

Deep wildness is not nonsense.

It is a period of enormous magical tolerance.

At deep wildness:

- Levitation may become ordinary travel.
- Healing may respond to intent.
- Fire may answer desire.
- Concealment may require only image or will.
- Songs may affect weather.
- Doors may open because a person knows where they mean to go.
- Children may perform magic without formal training.
- Cultural interfaces blur.
- Tools become less necessary.
- Magic becomes fantastical by ordered standards.

But this ease is also a warning.

When magic becomes as simple as “I want to levitate,” the pendulum is running out of momentum on the wild side.

Eventually the tolerance narrows again. Intuitive magic becomes less reliable. Traditions formalize. Schools return. Tools become necessary. Formula hardens. Order rises again.

## 17.7 Wildness Is Relative

“Wild magic” does not mean magic is random.

It means the world requires less exactness.

Relative to an ordered age, this feels wild.

Relative to deeper wildness, the early transition may still seem rigid.

This distinction is critical.

## 17.8 The Doom Engine Gradient

The pendulum’s slowing swing is anchored locally by a massive, unintentional epicenter deep within the western continent: the **Doom Engine**.

The Doom Engine is not necessarily a machine built with intent. It may be:

- A collapsed magical-industrial complex.
- A failed ordered formula on continental scale.
- A reality wound.
- A sanctuary that became an engine by accident.
- A ritual whose Ghost Term never resolved.
- A convergence of phase pressure.
- A city or cave system transformed into a stabilizing scar.

Proximity to the Doom Engine does not grant godlike power.

It subtly widens the tolerances of reality.

This can manifest as:

- Slightly increased spell duration.
- Damaged inscriptions working when they should fail.
- Hybrid cultural practices becoming stable.
- Broken tools behaving better than repaired ones.
- Spatial scars persisting.
- Survivor customs working for reasons eastern mages cannot parse.
- Anomalous sites becoming more common inland.

The Doom Engine Gradient should not be an explicit “+12% magic” UI from the beginning.

It should be discovered through pattern:

- Tools fail differently inland.
- Prior expedition notes contradict coastal tests.
- A cave song works only past a certain road marker.
- A broken inscription begins functioning near the hills.
- Companion interpretations change as evidence accumulates.
- The Archive synthesizes the concept only after enough fragments.

## 17.9 Gameplay Role of the Gradient

The Doom Engine Gradient can support:

- Reveal pacing.
- Regional magic variance.
- Hybrid tool unlocks.
- Stable anomaly distribution.
- Road weirdness.
- Cave settlement significance.
- Research synthesis.
- Risk/reward of going inland.
- A reason the west matters cosmologically.

It should be a strategic and narrative field, not just a damage multiplier.

---

# 18. The Calamity: Reality’s Five-Year Break

The calamity was the largest known break in reality.

It happened everywhere, but its physical epicenter was on the western continent.

Earlier breaks had occurred before. They were brief: a second, then two, then three, then ten, then fifteen, then twenty-four. Not literal numbers necessarily, but the shape is right. Each break lasted longer than the previous pattern suggested.

Most people dismissed them.

They became omens, folk tales, religious episodes, academic controversies, navigational errors, or magical accidents.

Then the western calamity happened.

On the western continent, the break lasted nearly five years.

During those years, magic broke. Reality loosened. Causality failed. Space misbehaved. Biological inheritance changed. Some things became Lovecraft meets Alice in Wonderland meets Flatland.

This does not mean everything was equally impossible all the time. It means ordinary rules could not be relied upon. Some places were worse than others. Some practices failed. Some people adapted. Some communities survived by learning rules no ordered mage would recognize as rules.

## 18.1 Most Effects Faded

When reality reasserted itself, most impossible effects faded.

Buildings returned to ordinary geometry.

Some roads stopped leading through impossible angles.

Some transformations reverted.

Some magical storms ended.

Some creatures died because their altered forms could not persist.

Some places became ordinary again.

## 18.2 Some Effects Persisted

Not all effects faded.

Some changes persisted because they altered something that remained stable afterward.

The model:

A freak radiation event changes the genetics of people from Newfoundland so that their descendants are born with horns. The event ends. The radiation is gone. But the inheritance remains. Now there are horned people, and you know they or their ancestors come from Newfoundland.

The calamity produced similar persistent alterations.

They are not all active anomalies.

Many are stable consequences.

## 18.3 Persistent Biological Scars

Possible persistent biological changes:

- Horned human lineages.
- Altered eyes.
- Strange vocal ranges.
- Skin changes.
- Dentition changes.
- Extra joints.
- Unusual balance or spatial perception.
- Families sensitive to Ghost Term residue.
- Children who dream in accurate maps.
- Cave-adapted lineages.
- Animals with stable calamity-altered traits.
- Plants with impossible but now-heritable branching or fruiting patterns.

These are part of the world now.

They should not all be treated as monsters.

Some are ordinary people whose ancestors were altered.

## 18.4 Persistent Spatial Scars

Possible persistent spatial changes:

- A stair with thirteen steps going up and twelve going down.
- A chamber acoustically larger than its dimensions.
- A road shorter when walked in silence.
- A building whose foundation lines do not quite close.
- A cave system with stabilized impossible topology.
- A room where shadows fall toward a wall.
- A valley visible from above but difficult to reach by ordinary routes.
- A cliff path that has different risk depending on direction.
- A cave mouth that is easier to find when not directly searched for.

These should have learnable rules.

## 18.5 Persistent Magical Scars

Possible persistent magical changes:

- Inscriptions that work despite missing strokes.
- Broken tools that function better than repaired ones.
- Cisterns that purify water if approached with the right practice.
- Burial chambers that preserve memory traces.
- Thresholds that reject exact eastern formulas but respond to song or breath.
- Old devices that work only when operators stop being precise.
- Marks that appear decorative until viewed through altered light.
- Tools that permanently encode impossible behaviors acquired during the break.

## 18.6 Persistent Cultural Scars

Survivor communities may have adapted to post-break rules.

Their practices may look irrational to eastern observers but actually encode survival.

Examples:

- Taboos around certain roads.
- Songs that stabilize cave spaces.
- Kinship rules built around altered bloodlines.
- Refusal to repair certain cracks because the crack is functional.
- Ritual mispronunciations that are not mistakes.
- Settlement layouts adapted to spatial scars.
- Burial customs that prevent memory residue from spreading.
- Children taught not to look at certain angles.
- Food practices based on altered plants or animals.

The player should learn to respect these practices as data.

---

# 19. Miracle Figures and Phase Memory

Ancient folk tales across the world speak of miracle-workers:

- A man who could raise the dead.
- A man who raised himself.
- A person who walked on water.
- A saint who turned water to wine.
- A healer who cured the sick by touch.
- A prophet who summoned food from nowhere.
- A drowned king who returned.
- A river woman who crossed floods without sinking.
- A child whose songs healed fever.
- A trickster who survived execution repeatedly.
- A cave elder who fed a refuge during famine.

Some stories are false.

Some are exaggerated.

Some are theology.

Some are politics.

Some are poetry.

But some are basically true.

A person who raised the dead, walked on water, turned water to wine, healed the sick, or summoned food may have been a real intuitive practitioner living near a collapse, when reality’s required precision was widening dramatically.

In a more ordered age, those acts would require impossible exactness, specialized tools, inscriptions, infrastructure, or cultural practices that no one retained.

Near collapse, reality accepted approximation.

Their talent, intent, speech, rhythm, confidence, symbol, and embodied imagination were enough.

They were not breaking reality.

Reality was already bending.

## 19.1 Why Miracle Traditions Matter

Miracle traditions are phase memory.

They preserve evidence of prior transitions.

Ordered scholars may dismiss them because modern formulaic magic cannot reproduce them. They are correct that their current methods cannot reproduce them. They are wrong about what that means.

The expedition may discover that old stories were not merely superstition.

They were historical evidence of magical tolerance changing.

## 19.2 Tone Rule

Do not deflate miracle stories with “it was just magic.”

The correct tone is:

> The stories were true, but truth is stranger than doctrine. He was real. He was gifted. And the world was already coming apart.

This preserves awe.

---

# 20. Caves and Deep Systems

Caves should be varied.

The world does not scale with the player. Diving into a cave is always a risk/reward calculation where the player weighs the extraction of knowledge against physical danger.

## 20.1 Cave Categories

Possible cave categories:

- Shallow natural cave.
- Animal den.
- Water cave.
- Guano cave.
- Burial cave.
- Shelter cave.
- Refuge cave.
- Worked cave.
- Deep shaft system.
- Petra-like carved settlement.
- Ancient ritual cave.
- Spatial scar cave.
- Phase sanctuary.
- Deep-time habitation site.
- Ghost-Term saturated system.
- Cave with no obvious value.
- Cave that appears boring until deep survey.

## 20.2 Cave Survey

The player should classify caves through survey:

- Airflow.
- Water.
- Depth.
- Human traces.
- Animal traces.
- Worked stone.
- Smoke.
- Tool marks.
- Inscriptions.
- Acoustic behavior.
- Altered geometry.
- Burial context.
- Magical readings.
- Route potential.

## 20.3 Deep-Time Layers

Caves should hold layers:

- Geological layer.
- Deep pre-calamity occupation.
- Ancient cave-city layer.
- Calamity refuge layer.
- Post-calamity survivor layer.
- Previous expedition layer.
- Current expedition layer.

The player should learn to read layers.

A cave is not “level 1.”

It is an archive.

---

# 21. Reveal Ladder

The player should not begin with cosmic truth.

He should begin with practical problems and quiet evidence.

## 21.1 Surface Reveals

1. The expedition lands at the dead port.
2. The port is ruined but not untouched.
3. There is evidence of people after the calamity.
4. There is evidence of previous expeditions.
5. There may have been more than one previous expedition.
6. The base must survive: water, food, shelter, security, morale.
7. The ancient road network still structures the land.
8. Inland settlements show staged collapse, not instant annihilation.

## 21.2 Road and Settlement Reveals

9. Roads were logistical, ceremonial, and possibly magical.
10. Waystations or road shrines encode survival knowledge.
11. Some road segments behave strangely due to stable scars.
12. A settlement may contain hostile occupants with valuable knowledge.
13. Data extraction becomes more important than clearing enemies.
14. Predator movement is tied to supply lines, not random encounters.

## 21.3 Cave and Historical Reveals

15. The first caves may be ordinary.
16. Some caves show human use.
17. Cave refuges confirm part of the oral history.
18. Some cave sites were inhabited before the calamity.
19. Petra-like cave settlements reveal organized cave civilization.
20. Deep-time sites reveal far older sophistication.
21. Ancient cave peoples understood magic differently, not primitively.

## 21.4 Calamity Reveals

22. Some western anomalies are stable, not active hallucinations.
23. The calamity lasted far longer in the west than in the east.
24. The west was the physical epicenter.
25. The break altered inheritance, geography, tools, and culture.
26. Not all effects faded.
27. Some survivor customs encode post-break rules.

## 21.5 Magical-Cosmological Reveals

28. Wildness means widening tolerance, not pure randomness.
29. Ordered magic produces a hidden deficit: the Ghost Term.
30. The Ghost Term accumulates or embeds in reality.
31. Maximal Order produces brittleness.
32. The western calamity was a major break near the ordered extreme.
33. The Doom Engine Gradient widens magical tolerance inland.
34. The east is still moving toward greater wildness but does not understand it.
35. Miracle traditions are evidence of earlier phase transitions.
36. The expedition may be discovering how to survive the next age.
37. The player must decide what to report, hide, repair, exploit, preserve, or seal.

---

# 22. What the Game Is Not

This section prevents drift.

The game is not:

- A generic dungeon crawler.
- A pure colony sim.
- A high-magic spell combat game.
- A loot treadmill.
- A linear cinematic adventure.
- A pure archaeology lecture.
- A survival crafting grind.
- A monster zoo.
- A base-management spreadsheet with occasional walking.
- A magic programming puzzle game as its main identity.
- A GPU simulation showcase with thin gameplay.
- A game where every cave has treasure.
- A game where every anomaly is random nonsense.
- A game where all cultures are cosmetic reskins.
- A game where ancient peoples are treated as primitive because they lack eastern notation.
- A game where every enemy must be fought.
- A game where settlement consequences can be ignored.
- A game where companions are interchangeable stat bundles.

---

# 23. Design Principles

## 23.1 Leadership Creates Cost

Every field choice costs base progress.

Every base choice costs exploration time.

Every person and tool has opportunity cost.

## 23.2 The World Is a Buried Human Landscape

The continent is not a wilderness map with dungeons.

It has roads, settlements, farms, waterworks, shrines, quarries, graves, paths, caves, memories, and scars.

## 23.3 The Past Has Layers

Locations often belong to multiple time periods.

A cave can be geological, ancient, civic, refuge, post-calamity, prior-expedition, and current-expedition all at once.

## 23.4 Magic Is Practical Before It Is Spectacular

Magic helps people see, preserve, bind, measure, travel, ward, translate, conceal, heal, and survive.

Combat magic is secondary.

## 23.5 Magic Is Deterministic but Culturally Encoded

Different cultures access the same underlying law through different partial interfaces.

Translation is difficult because no one understands the full mechanism.

## 23.6 Wildness Is Tolerance, Not Randomness

As wildness increases, the world accepts looser magical approximations.

This can empower people, destabilize institutions, and resurrect miracle-like possibilities.

## 23.7 Persistent Weirdness Has Rules

A persistent anomaly should satisfy three conditions:

1. It originated during a break.
2. It changed something that could remain stable afterward.
3. It now has rules the player can learn.

## 23.8 Knowledge Changes Play

Information must unlock options.

Discovery is not just lore.

It is physically deposited, processed, and turned into action.

## 23.9 Simulation Must Be Legible

The player should be able to infer from clues.

Simulation should create mystery, not opaque noise.

## 23.10 Boring Places Are Allowed

Not every cave, ruin, or road branch is dramatic.

This makes real discoveries matter.

## 23.11 The Indifferent Simulation

The continent does not scale to the player.

The player must respect geographical boundaries and execute strategic data extraction raids rather than assuming every location contains a level-appropriate challenge.

## 23.12 Moonshots Must Degrade Gracefully

Every advanced simulation dream needs a simple version that preserves gameplay purpose.

---

# 24. True Targets

These are the project’s real commitments.

They should define the game even if no moonshot is ever completed.

## True Target 1: Expedition Leadership and Couples Draft

The player commands a small expedition, not an army.

The roster is drafted through interlocking family units, often couples, forcing the player to choose economic stability, academic speed, field strength, magical expertise, or logistical resilience.

Taking a person or tool into the field removes them from base work.

Losing a bonded spouse creates cascading morale failures.

## True Target 2: Ruined Harbor Base

The campaign begins at a ruined port city on the western continent.

The base grows out of reclaimed stone buildings and improvised repairs.

The port contains practical resources, historical evidence, post-calamity clues, and prior expedition traces.

## True Target 3: Survival Logistics Without Crafting Grind

Food, water, shelter, health, security, and morale matter.

The player makes meaningful strategic decisions, not personally grinds raw materials.

## True Target 4: Ancient Road Progression

At least one ancient path leads inland.

Finding, clearing, securing, and following it is a major campaign arc.

Roads are logistical lifelines that support travel, supply, Waystations, predator pressure, and reveal pacing.

## True Target 5: Surface Exploration Matters

The surface world must be important before caves dominate.

The player must scout resources, terrain, ecology, roads, settlements, ruins, predator territories, and prior expedition traces.

## True Target 6: Caves Are Varied and Sometimes Boring

Caves should not all be dungeons.

Some are mundane. Some are useful. Some are false leads. Some are historically profound. Some become important only after deeper survey.

## True Target 7: Petra-Like Cave Civilizations

The player eventually discovers cave systems that were homes, cities, sanctuaries, and refuges.

They reveal pre-calamity and deep-time sophistication.

## True Target 8: Deep-Time Archaeology

The game uncovers evidence of very old human or human-adjacent sophistication.

This challenges eastern assumptions about history, civilization, and magic.

## True Target 9: Knowledge as Loot and Central Archive

The most important rewards are discoveries that physically return to the Base Camp’s Central Archive.

Scholars and specialists synthesize fragments into Concepts that unlock new routes, hybrid tools, field procedures, and strategic options.

## True Target 10: Practical Cultural Magic

The player begins with eastern inscription magic.

Other cultures use different interfaces: song, gesture, breath, geometry, circles, knots, chamber acoustics, and place-bound practice.

Magic is deterministic but culturally encoded.

The player mostly uses magical tools, research, repair, and interpretation rather than programming spells.

## True Target 11: Pendulum Cosmology and Doom Engine Gradient

Magic moves through vast cycles between Maximal Order and Maximal Wildness.

The western continent houses an epicenter, the Doom Engine, that anchors a gradient field.

Moving deeper inland gently widens magical tolerances, enabling accidental hybridization of cultural magics and stable scars.

## True Target 12: The Ghost Term

Formulaic ordered magic produces an unseen mathematical deficit that accumulates in reality.

The player discovers it through evidence, not exposition.

## True Target 13: Wildness as Fuzzy Precision

Wild magic means the precision required to affect reality becomes fuzzier.

This enables fantastic intuitive magic, but it also signals a nearing pendulum reversal.

## True Target 14: Stable Scars of Broken Reality

The western continent bears persistent biological, spatial, magical, and cultural scars from the five-year break.

These scars are not random. They have learnable rules.

## True Target 15: Miracle Figures as Phase Evidence

Ancient miracle-workers were often real gifted people living near magical transitions.

Their stories preserve evidence of widening tolerance and prior collapses.

## True Target 16: Light, Sound, Scent, and Terrain Gameplay

Light, sound, scent, and terrain physically drive exploration, stealth, combat, investigation, and horror.

Apex predators can actively hunt expedition scent across the overland map.

## True Target 17: Walkable Settlement Consequences

The base is a physical, walkable space that changes based on discoveries, assignments, injuries, road access, Waystations, morale, social bonds, and resources.

The settlement can physically halt its economy if roads are blocked, a key person dies, or social trust collapses.

## True Target 18: Companion Expertise

Companions matter in base work and field interpretation.

Their skills affect what the player can safely do and correctly understand.

## True Target 19: Reveal-Driven Campaign

Progression is structured through discoveries, data extraction raids, road access, Archive synthesis, and field evidence, not simply dungeon depth or character level.

## True Target 20: Deterministic, Data-Driven Simulation

The game preserves deterministic behavior, data-driven state, and performance-conscious architecture.

---

# 25. Planned Systems Cluster

This section converts the previously unsupported concepts into a coherent future design cluster.

They are not current implementation claims. They are named design targets.

## 25.1 Infrastructure System

Purpose:

Manage roads, Waystations, blockages, travel modifiers, logistics, and base-to-field reach.

Core state:

- Road segment status.
- Blockage type.
- Repair progress.
- Waystation condition.
- Supply access.
- Travel cost.
- Scent output.
- Weather damage.
- Labor assignment.
- Required expertise.
- Safety rating.

Player-facing effect:

- Roads open or close practical campaign space.
- Waystations extend reach.
- Blocked roads can strand parties.
- Infrastructure neglect creates danger.
- Labor invested today changes tomorrow’s expedition options.

## 25.2 Morale and SocialBond System

Purpose:

Make the roster socially consequential.

Core state:

- Individual morale.
- Trust in leader.
- Fear.
- Grief.
- Partner bond.
- Friendship.
- Rivalry.
- Duty pressure.
- Refusal threshold.
- Recovery conditions.

Player-facing effect:

- Deaths change labor behavior.
- Bonded survivors may stop working.
- Some companions refuse or demand missions.
- Social crisis becomes logistical crisis.
- Strong leadership can stabilize, but not erase, consequences.

## 25.3 Research System and Central Archive

Purpose:

Turn discoveries into mechanics.

Core state:

- KnowledgeFragments.
- Artifact records.
- Translation progress.
- Concept recipes.
- Specialist availability.
- Tool requirements.
- Experimental risk.
- Archive facility state.
- Cross-reference links.

Player-facing effect:

- Knowledge is loot.
- Returning to base matters.
- Research requires people and tools.
- Eureka moments unlock new systems.
- Field evidence changes strategy.

## 25.4 Ancient Road and Waystation System

Purpose:

Make the surface campaign a logistics and discovery arc.

Core state:

- Road graph.
- Segment condition.
- Fork confidence.
- Survey status.
- Waystation placement.
- Supply range.
- Route safety.
- Predator pressure.
- Historical site links.
- Anomaly flags.

Player-facing effect:

- The player follows human infrastructure into the unknown.
- Ancient roads reveal civilization.
- Waystations extend but also expose the expedition.
- Road weirdness foreshadows the calamity.

## 25.5 Overland Scent-Gradient Threat System

Purpose:

Replace random overland combat with legible predator pressure.

Core state:

- Base scent source.
- Waystation scent source.
- Field-party trail.
- Supply-route trail.
- Wind/weather modifiers.
- Predator territory.
- Apex predator hunger/state.
- Masking measures.
- Carcass/scavenger attractors.

Player-facing effect:

- The player can infer why danger approaches.
- Supply lines become vulnerable.
- Scent masking and route choice matter.
- Predators create emergent siege scenarios.

## 25.6 Doom Engine Gradient System

Purpose:

Provide a spatial-cosmological reason the west matters.

Core state:

- Regional wildness tolerance.
- Ghost Term saturation.
- Ordered formula brittleness.
- Hybridization allowance.
- Stable scar probability.
- Sanctuary or bleed-off zones.
- Doom Engine distance or influence.

Player-facing effect:

- Inland movement changes magical behavior.
- Hybrid tools become possible.
- Anomalies follow a hidden logic.
- Research connects geography to cosmology.

## 25.7 Magic Hybridization System

Purpose:

Make cultural translation a source of power.

Core state:

- Cultural interface tags.
- Inscription features.
- Breath/song/gesture/geometry features.
- Material compatibility.
- Site conditions.
- Wildness tolerance.
- Failure modes.
- Discovered Concepts.

Player-facing effect:

- The player combines evidence, not spell components.
- Hybridization is unlocked by understanding.
- Tools, companions, and place matter.
- Magic remains practical and archaeological.

---

# 26. Moonshots

Moonshots are long-term ambitions.

They should inspire architecture but never block the core game.

## Moonshot 1: Massive Ecological Simulation

Track thousands or tens of thousands of animals across the continent.

Gameplay:

- Hunting pressure changes prey.
- Predators follow prey toward camp.
- Overhunting causes scarcity.
- Animal trails reveal water or caves.
- Carcasses attract scavengers.
- Smoke and sound alter movement.
- Magical scars distort ecology.

Fallback:

Regional population counters, event tables, and local spawns.

## Moonshot 2: Dijkstra-Field World Simulation

Use Dijkstra maps and flow fields for world processes, not just movement.

Fields:

- Water.
- Smoke.
- Gas.
- Heat.
- Cold.
- Scent.
- Sound.
- Disease.
- Fear.
- Rumor.
- Patrol pressure.
- Predation pressure.
- Human traffic.
- Soul residue.
- Calamity influence.
- Ghost Term load.

Fallback:

Local active-region fields and coarse region summaries.

## Moonshot 3: Hydrology and Flooding

Water is a real actor.

Gameplay:

- Rain fills cisterns.
- Flooding blocks caves.
- Repairing aqueducts transforms settlement survival.
- Water reveals or hides routes.
- Bodies contaminate sources.
- Old waterworks become strategic objectives.

Fallback:

Discrete zone states: dry, damp, flowing, flooded, contaminated, potable.

## Moonshot 4: Gas, Smoke, Airflow, and Breath

Caves have atmospheres.

Gameplay:

- Torches fail in bad air.
- Smoke reveals hidden shafts.
- Low chambers collect gas.
- Some magic requires still air.
- Some creatures hunt breath or heat.
- Airflow hints at hidden chambers.

Fallback:

Localized gas hazards, airflow clues, and scripted chamber states.

## Moonshot 5: Settlement-Scale Social Simulation

The 24-person expedition develops socially.

Gameplay:

- People want to leave.
- People hide evidence.
- People volunteer or refuse.
- Some demand exploitation.
- Some demand sealing caves.
- Discoveries shift loyalties.

Fallback:

Morale, trust, fear tags, relationship tags, and conflict events.

## Moonshot 6: Deep Archaeological Stratigraphy

Sites are generated as layered archaeological records.

Gameplay:

- Excavation reveals history gradually.
- Poor digging destroys context.
- Specialists disagree.
- Artifact position matters.
- The player can draw wrong conclusions.

Fallback:

Location phase tags and curated evidence clusters.

## Moonshot 7: Memory, Ghosts, and Soul Fields

The world remembers.

Gameplay:

- Lamps reveal old movement.
- Burial places affect morale and magic.
- Some creatures follow death residue.
- Old roads are easier to find because of repeated passage.
- Wrong excavation disturbs a place.
- The calamity damaged the normal flow of the dead.

Fallback:

Lore tags, map overlays, rare tool interactions, and site-specific events.

## Moonshot 8: Ten-Thousand-Agent Historical Echoes

Simulate past movements to generate evidence.

Use cases:

- Exodus flow.
- Refugee bottlenecks.
- Previous expedition paths.
- Burial clusters.
- Abandoned carts.
- Sealed doors.
- Cave refuge use.
- Collapse sequences.

Fallback:

Procedural templates driven by historical phase tags.

## Moonshot 9: GPU-Accelerated Continental Simulation

Use GPU-capable data processing for large simulation layers.

Candidate workloads:

- Field propagation.
- Cellular automata.
- Hydrology.
- Gas diffusion.
- Heat maps.
- Animal pressure.
- Vegetation growth.
- Erosion.
- Road/path cost maps.
- Sound/scent propagation.
- Multi-agent coarse movement.
- Phase pressure.
- Ghost Term accumulation.

Caution:

Do not depend on a specific GPU stack as a design foundation.

Architecture implication:

Keep simulation state columnar, chunkable, deterministic, separable by region, and backend-agnostic so CPU and GPU implementations can coexist later.

Fallback:

CPU-friendly sparse updates, local active windows, and region summaries.

## Moonshot 10: Living Lost Continent

The continent changes between expeditions.

Gameplay:

- Brush reclaims roads.
- Hunting changes animal routes.
- Smoke attracts attention.
- Floods open new cave paths.
- Inland groups notice the expedition.
- Predators learn routes to camp.
- Wards weaken over time.

Fallback:

Turn-based regional events and procedural changes.

## Moonshot 11: Comparative Thaumaturgy Engine

A hidden deterministic magic model underlies all cultural interfaces.

Gameplay:

- Scholars propose translation theories.
- Experiments test correspondences.
- Failed translations create partial effects.
- Hybrid tools emerge.
- Ancient sites become magical laboratories.

Fallback:

Tags, prerequisites, research projects, and curated adaptation outcomes.

## Moonshot 12: Order/Wildness Phase Field

Track magical phase pressure across regions.

Gameplay:

- Ordered tools become reliable but brittle in high-order zones.
- Wild practices become adaptable in wild zones.
- Overuse of formulaic magic increases local Ghost Term load.
- Ancient sanctuaries bleed off deficit.
- Hybrid tools bridge phase gradients.
- Some regions respond intuitively.

Fallback:

Region tags: Stable Ordered, Brittle Ordered, Transitioning, Wild-Stirred, Deep Wild, Sanctuary, Ghost-Term Saturated.

## Moonshot 13: Persistent Anomaly Ecology

Reality-break effects alter stable systems that propagate over time.

Fallback tags:

- Horned Lineage.
- Spatial Scar.
- Breath-Sensitive Chamber.
- Stable Wild Residue.
- Inheritance Altered.
- Tool-Break Beneficial.
- Sound-Geometry Mismatch.
- Cave-Time Distortion.
- Ghost-Term Saturated.
- Wild-Tolerant Practice.

## Moonshot 14: Procedural Miracle History

Generate old miracle traditions as distorted memories of prior phase events.

Gameplay:

- Folk stories contain clues.
- Shrines encode phase data.
- Miracle sites behave oddly.
- A saint may be a historical intuitive practitioner.
- Player reconstructs what happened.

Fallback:

Curated folk-tale library with tags linking to site types and phase events.

---

# 27. First Major Milestones

This is not a production schedule, but the North Star implies a sensible order.

## Milestone 1: The Landing

Build the ruined harbor and expedition roster.

Include:

- Landing sequence.
- 24-person roster.
- Couples Draft.
- Base resource state.
- Initial assignments.
- Ruined stone buildings.
- First evidence of post-calamity habitation.
- First evidence of prior expedition.
- Basic look/examine.
- Simple daily loop.

## Milestone 2: The Base and Local Survey

Build survival logistics.

Include:

- Food/water/shelter/security/morale.
- Local scouting.
- Resource discovery.
- Companion assignment.
- Tool availability.
- First practical magic tools.
- Night events.
- Social bond status.
- Basic Central Archive shell.

## Milestone 3: The Ancient Path

Build road discovery and clearing.

Include:

- Old road segments.
- Brush clearing.
- Route security.
- Waypoints.
- First Waystation.
- Road forks.
- First inland site.
- Risk tradeoffs.
- Assignment consequences.

## Milestone 4: The First Settlement

Build an inland settlement with staged-collapse evidence.

Include:

- Post-calamity survival evidence.
- Previous expedition traces.
- Practical resources.
- Historical ambiguity.
- Possible hostile occupants.
- Data extraction objective.
- Companion interpretation.

## Milestone 5: The First Caves

Build cave survey before cave civilization.

Include:

- Ordinary caves.
- One worked cave clue.
- Rope/shaft/airflow mechanics.
- Light/sound/scent gameplay.
- Animal threat.
- False lead.
- Reason to return.

## Milestone 6: The First Cave Settlement

Build Petra-like cave content.

Include:

- Carved dwellings.
- Cistern.
- Inscriptions.
- Refuge layer.
- Older layer.
- Phase anomaly hint.
- Cultural magic evidence.

## Milestone 7: The First Cosmological Reveal

Introduce Ghost Term and wildness tolerance indirectly.

Include:

- Eastern tool failure.
- Local practice success.
- Stable anomaly.
- Companion disagreement.
- Prior expedition journal.
- Miracle/folk-tale tie-in.
- First Central Archive Eureka.
- First hint of Doom Engine Gradient.

---

# 28. Final Player Experience

The player begins on the deck of a ship before dawn. The western continent is a dark line ahead. No one cheers when land appears.

By midday, crates are coming ashore into a ruined harbor plaza. Grass grows through old paving stones. Stone buildings stand roofless. The wooden city is gone. A carved harbor marker faces the sea. A dry fountain is full of windblown soil. The river may still run, or perhaps only its old channel remains.

Twenty-four people remain behind.

The ship leaves.

The first day is command. The player chooses where supplies go, who tests water, who guards, who inspects the stone buildings, who clears sleeping space, and who begins inventory.

The first mystery is small: soot in an old fireplace.

Not ancient soot.

Later, a repaired wall. A rusted eastern buckle. A broken crate stamped with a mark no official record mentions. Someone has been here since the calamity. Perhaps several someones.

The next days are survival. The base needs water, food, shelter, and trust. The player sends hunters, scouts, scholars, laborers, guards, craftspeople, and mages to work. Every useful person is scarce. Every absence matters. Every couple’s skills matter.

The ancient road is found under brush.

Opening it takes days. Then weeks. It leads to a watch post, a shrine, a broken culvert, an abandoned hamlet, a fork, and signs of people who lived long after they were supposed to be gone.

A Waystation extends the expedition’s reach.

Then something follows the scent of repeated travel.

The surface campaign becomes a contest of logistics, risk, and inference. The player does not fight random encounters. He sees evidence: prints, carcasses, missing food, broken brush, disturbed markers, a guard’s report, a scent-masked road that remains safe while an unmasked one becomes deadly.

Eventually, the road reaches hills.

The first cave is disappointing: wet stone, animal smell, guano, and a dead end.

The second has airflow but no obvious passage.

The third has a worked threshold half buried by a slide.

Inside, the game changes.

Light matters. Sound matters. Scent matters. Ropes matter. Companions matter. The player hears water below. A thrown stone takes too long to land. The hidden-light lantern keeps predators from seeing the party’s light, but now companions cannot share what the leader sees. A cracked inscription works when it should not. A local carving resembles eastern notation only if viewed as song rather than writing.

The expedition finds a refuge chamber: storage jars, child marks, smoke, bones, and an attempt to seal a deeper stair from the inside.

Below that, older rooms.

Below that, a cave settlement.

Below that, deep-time evidence of people who understood the caves before the east’s histories begin.

Then the first stable impossibility: a stair with different counts depending on direction. A horned lineage in old burial art. A tool that works better broken. A chamber that answers a sung phrase no eastern scholar can parse. Evidence that the calamity lasted not days, not weeks, but years.

The player returns to base changed.

The evidence goes into the Central Archive. The scholar argues with the practical mage. The archivist finds a pattern. The mason points out that the road shrine and cave threshold use the same geometry. A grieving partner refuses field work. A hunter warns that the supply route is drawing something large. The hidden-light lantern is needed in three places at once.

A Eureka moment unlocks a new field procedure.

The settlement reacts. Some want to push deeper. Some want to stop. Some want to exploit. Some want to pray. Some want to hide the truth from the east. Some begin testing magic they were never trained to use.

The player realizes the mission is not simply rediscovering a continent.

It is discovering why the old world broke.

And perhaps why the current one is beginning to loosen.

---

# 29. The Deepest Statement of the Game

At the practical level, the game is about keeping an expedition alive.

At the historical level, it is about discovering what happened to a lost continent.

At the magical level, it is about learning that culture is only a partial interface with deterministic law.

At the cosmic level, it is about a civilization built on ordered magic encountering evidence that order is temporary.

At the human level, it is about responsibility: the leader who paid to uncover the past must decide what the future is allowed to know.

The North Star is:

> Lead the expedition. Rebuild the foothold. Follow the roads. Read the ruins. Descend into the caves. Learn what survived. Learn what changed. Learn why the west broke. Learn whether the east can survive what comes next.

---

# 30. Implementation Boundary Note

This document intentionally includes both current-direction material and future systems.

For implementation planning, classify items this way:

## Current Foundation

Use existing repo systems as technical leverage:

- `game/`
- `engine/`
- `Dungeon/`
- `pathfinding/`
- `utils.game_rng.GameRNG`
- `game/ai/`
- `auto/` as GOAP tuning harness
- `ai/` as community AI R&D
- `game/skills/`
- top-level `skills/`
- `magic/`
- `simulation/`
- `worldgen/`

## Near-Term Design Targets

Prioritize playable systems:

- Landing.
- Roster.
- Couples Draft.
- Base assignment.
- Ruined harbor.
- Local survey.
- Ancient road.
- First Waystation.
- KnowledgeFragment.
- Central Archive shell.
- Light/sound/scent cave survey.
- First practical magic tools.

## Future Design Systems

Develop as focused architecture proposals:

- Infrastructure system.
- Morale and SocialBond system.
- Research and Central Archive system.
- Ancient Road / Waystation logistics.
- Overland scent-gradient threats.
- Doom Engine Gradient.
- Magic hybridization.
- Comparative thaumaturgy.
- Phase-field and Ghost Term simulation.

## Rule for Future Work

Every future system should answer four questions before implementation:

1. What player decision does this create?
2. What visible consequence does it produce?
3. What simpler deterministic fallback preserves the gameplay?
4. Which current repo system does it extend rather than duplicate?

# Persistent Player-Scale Map Systems: CDDA-like Technical Overview

Technical comparison of map architectures and gameplay loops for games that need a **persistent map at player scale**: a world the player can physically traverse, alter, revisit, and reason about over time.

The center of gravity is **Cataclysm: Dark Days Ahead (CDDA)**: a strategic overmap feeds into dense local tile simulation, while the local world preserves meaningful player-scale state. The broader purpose of this document is to identify neighboring designs that solve related problems: persistent terrain and object state, exploration across scales, procedural spatial content, travel friction, logistics, encounter generation, and emergent survival pressure.

The target lens is deliberately narrower than “interesting procedural maps.” The most relevant examples are systems where the map is not just a menu, scenario selector, or temporary combat arena. The map should function as a **durable play surface**: buildings remain looted, roads remain blocked, bases remain built, fires leave consequences, faction control can change, and route knowledge retains value.

Verticality is desirable for the target solution because basements, rooftops, caves, bridges, towers, tunnels, and stacked interiors create richer navigation and persistence problems. However, Z-axis support is not required for an example to be useful. A two-dimensional system can still be highly relevant if it demonstrates player-scale persistence, chunking, route pressure, local simulation, or macro-to-local generation.

---

## What “CDDA-like” Means Here

“CDDA-like” does not mean “post-apocalyptic roguelike.” It means a system where the map is not just scenery, a level list, or a backdrop for encounters. The map is a **persistent, stateful rules surface at player scale**.

For this document, the strongest fit is a game where the player can move through local space, interact with concrete objects and terrain, leave persistent changes behind, and later return to those changed places. Strategic abstractions are valuable when they help generate, summarize, navigate, or stream that player-scale world.

A CDDA-like or CDDA-adjacent map system usually has several of these properties:

* **Player-scale locality**: The player interacts with concrete spaces: rooms, roads, fields, caves, roofs, vehicles, doors, shelves, bodies, fires, furniture, and terrain.
* **Persistent state**: Explored regions, destroyed buildings, dead NPCs, looted shelves, base construction, blocked roads, faction changes, ecological changes, and player-built infrastructure persist.
* **Multiple spatial scales**: A strategic layer for long-distance understanding can coexist with a tactical/local layer for detailed interaction.
* **Procedural or semi-procedural content**: Locations, encounters, loot, factions, structures, weather, or local states are generated from rules.
* **Travel as gameplay**: Distance, terrain, time, visibility, noise, supplies, fatigue, and transport alter decisions.
* **Information asymmetry**: The player sees partial maps and makes decisions under uncertainty.
* **Simulation density**: Tiles, hexes, chunks, rooms, or nodes host meaningful systems: items, creatures, fields, temperature, scent, sound, fire, disease, faction control, traffic, or resource depletion.
* **Local detail from global context**: A “town,” “forest,” “lab,” “ruin,” “road,” or “river” on the macro layer resolves into concrete geometry, objects, inhabitants, and hazards on entry.
* **Optional verticality**: Z-levels, stacked interiors, caves, roofs, shafts, and bridges add value but are not mandatory for an example to inform the solution.

---

## Core Technical Axes

### 0. Target Fit: Persistent Player-Scale Map

Before comparing architectures, the most important filter is whether the map supports persistent play at the scale of the character.

Strong target fit:

* The player can physically traverse local spaces rather than only select destinations.
* The world stores enough state that revisiting a location is meaningful.
* Map changes affect later route planning, safety, logistics, or available actions.
* Local detail is not disposable; it can be modified, depleted, damaged, occupied, fortified, or remembered.
* Macro-scale abstractions exist to support the local world, not replace it.

Weak target fit:

* The map is primarily a level select screen.
* Encounters are generated, resolved, and discarded with little spatial memory.
* Tactical maps exist only for battles and do not preserve broader world state.
* Travel is represented only as a cost between abstract nodes.

Weak-fit systems can still be useful comparisons, but they should be treated as sources of isolated patterns rather than full architectural models.

### 1. Scale Model

The most important architectural decision is how the game represents space across scales.

* **Dual-scale overmap + local map**: CDDA, Caves of Qud, Dwarf Fortress Adventure Mode, RimWorld caravans, Battle Brothers.
* **Seamless chunked world**: Project Zomboid, Kenshi, Minecraft, Factorio.
* **Single abstract map with encounter resolution**: NEO Scavenger, Sunless Sea, Roadwarden, many hexcrawls.
* **Modular revealed map**: Mage Knight, some board games, tile-laying exploration games.
* **Graph or node map**: Roadwarden, King of Dragon Pass/Six Ages, many narrative survival games.
* **GIS-style tiled world**: Real-world mapping systems, simulation sandboxes, large streamed open worlds.

For the target solution, dual-scale and seamless chunked worlds are the strongest architectural families because both can preserve player-scale detail. Abstract maps, pointcrawls, and tactical battle maps are still valuable, but mainly as references for route costs, encounter pacing, information economy, or strategic presentation.

### 2. Z-Axis and Spatial Stacking

Z-axis support is desirable but should not dominate the comparison.

Useful Z-axis problems include:

* Stacked interiors: basements, upper floors, rooftops, towers, malls, hospitals, apartment blocks.
* Subsurface networks: caves, mines, sewers, bunkers, subway tunnels, labs.
* Overpasses and bridges: entities can occupy different heights at the same X/Y position.
* Line of sight and sound across floors: stairwells, holes, shafts, windows, rooftops.
* Persistence across layers: a fire, collapse, flood, infestation, or faction occupation can move vertically.

However, many useful examples are essentially 2D. They remain relevant when they solve persistence, streaming, player-scale interaction, travel pressure, or map knowledge better than a 3D system.

### 3. Generation Timing

Procedural content can be generated at several points.

* **Worldgen upfront**: Dwarf Fortress, Caves of Qud, Daggerfall, many 4X games.
* **Lazy generation on discovery/entry**: CDDA mapgen, Minecraft chunks, Project Zomboid randomized building states.
* **Runtime encounter injection**: NEO Scavenger, Sunless Sea, tabletop hexcrawls.
* **Shuffled physical/randomized components**: Mage Knight tiles, hex-crawl encounter tables, board-game event decks.
* **Hand-authored base plus randomized state**: Project Zomboid, The Long Dark, Kenshi, many immersive sims.

### 4. Persistence Scope

A major difference between systems is what they remember.

* **Tile persistence**: Burned terrain, dropped items, corpses, fields, built structures.
* **Site persistence**: A settlement remembers relations, stock, destruction, or quests.
* **World persistence**: Faction wars, trade routes, weather, seasons, migrations, world history.
* **Soft persistence**: The world does not store every object, but stores enough flags and resources to imply continuity.
* **No or limited persistence**: Encounters are generated and resolved, then mostly discarded.

### 5. Information Economy

Maps also define what the player knows.

* **Fog of war**: Unknown terrain revealed through movement.
* **Surveyed vs unsurveyed layers**: A macro map may reveal roads while hiding basements, loot, or local threats.
* **Rumor-based discovery**: Taverns, notes, quests, landmarks, radio signals, and NPC reports add map markers.
* **Sensor or scouting systems**: Vision cones, sound propagation, weather, elevation, satellites, radar, caravans, drones.
* **Cartographic memory**: The character, not just the player, may have limited map knowledge.

### 6. Travel Friction

The key loop is often not “go there,” but “can you afford to go there?”

Friction sources include:

* Terrain movement cost.
* Hunger, thirst, warmth, fatigue, morale, wounds, disease.
* Time pressure, day/night cycles, seasons.
* Fuel, vehicle maintenance, pack weight, animal stamina.
* Random encounters, patrols, ambushes, weather events.
* Navigation errors, blocked roads, river crossings, mountains, hostile territory.
* Social access: faction borders, tolls, reputation, law, permits, safehouses.

---

## Cataclysm: Dark Days Ahead (CDDA)

### Map Architecture

CDDA uses a strong dual-scale architecture and is the baseline target example because its local world exists at player scale and persists after interaction.

* **Overmap layer**: A large strategic grid of overmap terrain identifiers (`oter_id`) representing roads, forests, fields, towns, labs, bunkers, rivers, swamps, evacuation shelters, military sites, and other points of interest.
* **Local map layer**: A dense square tile grid with Z-level support. Local terrain, furniture, fields, items, monsters, vehicles, traps, and structures are simulated at player scale and much higher resolution.
* **Submaps and map chunks**: The local reality is divided into manageable map pieces. The engine can load nearby sections around the player and unload distant sections while preserving state.
* **Verticality**: Basements, sewers, subway tunnels, rooftops, labs, towers, bridges, and multi-story buildings make local space three-dimensional. This is valuable for the target solution, but CDDA’s deeper lesson is persistence and semantic expansion, not merely Z-levels.

The key technical idea is that the overmap acts as a **semantic promise**. A hospital tile, mall tile, farm tile, lab tile, cabin tile, or road tile means the local mapgen system can instantiate a detailed local environment consistent with that macro symbol.

### Generation

CDDA combines authored data with procedural assembly.

* JSON mapgen definitions describe terrain, furniture, loot groups, monster groups, vehicles, traps, fields, and special cases.
* Palettes and reusable templates make repeated building types possible without hardcoding everything.
* Overmap specials place rare or complex locations such as labs, military installations, crashed vehicles, fungal blooms, refugee centers, mines, or unusual ruins.
* Map extras add localized events: roadblocks, wrecks, craters, corpses, campsites, ambushes, and environmental anomalies.
* Generation is mostly lazy: local detail is generated when an area becomes relevant.

This architecture supports a powerful modding model. New location types, terrain palettes, loot groups, and monster distributions can be added through data.

### Navigation and Scale

The player alternates between:

* **Local movement**: Turn-based, tile-by-tile movement with action costs.
* **Overmap reading**: Planning routes through roads, towns, forests, rivers, and dangerous regions.
* **Vehicle-based macro logistics**: Cars, bikes, armored vehicles, boats, and custom mobile bases alter the reachable world.
* **Z-level tactical movement**: Stairs, ladders, elevators, rooftops, basements, and underground networks create vertical risk.

Example: The overmap shows a mall. At the local level, that resolves into a large multi-chunk structure with storefronts, escalators or stairs, back rooms, locked doors, loot distributions, monster populations, and line-of-sight concerns.

### Simulation Layer

CDDA’s local map is one of the densest simulation surfaces in survival games.

* Items have volume, mass, material, condition, flags, charges, spoilage, temperature, and container relationships.
* Fields include smoke, fire, gas, acid, radiation, blood, scent, and other effects.
* Monsters and NPCs operate with AI, senses, faction relationships, and pathfinding.
* Vehicles are multi-tile dynamic entities made from parts with damage, fuel, batteries, cargo, engines, wheels, controls, turrets, and appliances.
* Time advances with every action. Weather, seasons, light, temperature, food spoilage, wounds, and fatigue create long-term consequences.

### Core Gameplay Loop

Explore overmap -> identify target -> enter local map -> scavenge/fight/craft/repair -> manage physiological and logistical pressure -> retreat or establish base -> expand range through vehicles, tools, skills, and map knowledge.

### Design Lesson

CDDA’s distinctive strength is the **semantic-to-simulation pipeline**: a high-level map label expands into a deeply interactive local environment. This gives the player strategic readability without sacrificing local complexity.

---

## Caves of Qud

### Map Architecture

Caves of Qud uses a dual-scale world structure.

* **World map**: A large, partly fixed, partly procedural overworld containing biomes, rivers, deserts, jungles, ruins, villages, caves, and major story locations.
* **Local zones**: Each world tile can be entered as a detailed local zone with creatures, objects, terrain, liquids, artifacts, and special features.
* **Vertical shafts and depths**: Underground levels, ruins, caves, and historical sites can extend downward or upward.

### Generation

Qud is hybrid rather than purely procedural.

* Major geography and some story-critical sites provide structure.
* Villages, ruins, factions, histories, sultans, artifacts, lairs, and local details are generated from seed-dependent systems.
* Procedural histories create lore artifacts and connections between places.

### Navigation and Scale

The world map enables fast traversal between known regions, but local maps remain essential for tactical interaction and discovery. Travel is constrained by terrain, faction risk, hostile wildlife, thirst, navigation skill, and special environmental conditions.

Example: A world-map ruin may resolve into a multi-zone historical site with named relics, faction-linked inscriptions, hazards, and generated enemies.

### Simulation Layer

Qud’s map simulation is less materially exhaustive than CDDA’s but more focused on **systemic identity**.

* Creatures, factions, mutations, cybernetics, liquids, gases, plants, machines, and psychic systems interact in surprising ways.
* Generated histories give sites symbolic and mechanical context.
* Reputation and faction relations affect encounters.

### Core Gameplay Loop

Traverse world map -> discover/enter sites -> read history and faction context -> fight, negotiate, loot, or exploit systems -> develop character build -> push deeper into dangerous regions.

### Design Lesson

Qud shows how a map can be both a survival/exploration surface and a **lore machine**. It uses procedural history to make generated places feel authored.

---

## Dwarf Fortress: Adventure Mode

### Map Architecture

Dwarf Fortress uses one of the richest multi-scale world models in games.

* **World map**: Procedural continents with climates, geology, rivers, civilizations, sites, caves, roads, wars, and histories.
* **Site maps**: Towns, fortresses, lairs, caves, tombs, towers, temples, camps, and ruins become detailed local spaces.
* **Local tactical space**: The player interacts at creature and object scale.
* **Historical layer**: Legends mode exposes the generated record behind the world.

### Generation

Dwarf Fortress world generation runs extensive simulation before play.

* Civilizations rise, migrate, fight, create artifacts, build sites, and leave ruins.
* Historical figures are born, die, gain reputations, inherit grudges, or become monsters.
* Local maps draw from geography and history, not just terrain templates.

### Navigation and Scale

Adventure Mode travel alternates between world-map movement and local site exploration. A village or fortress is not only a location marker; it contains named inhabitants, structures, social relationships, objects, and records.

### Simulation Layer

The simulation is extreme.

* Creatures have body parts, tissues, wounds, skills, beliefs, memories, preferences, needs, relationships, and social positions.
* Objects and artifacts have histories.
* Background civilizations and sites continue to evolve.
* Combat and injury are highly granular.

### Core Gameplay Loop

Travel world map -> enter site -> interact, quest, fight, steal, trade, investigate, or roleplay -> alter historical state -> move to another site.

### Design Lesson

Dwarf Fortress demonstrates a **history-first map architecture**: geography matters because historical simulation has acted upon it.

---

## Project Zomboid

### Map Architecture

Project Zomboid is not dual-scale in the CDDA sense. It uses a huge seamless isometric world.

* The map is divided into cells and chunks for streaming.
* The player physically traverses the world rather than jumping through an overmap.
* The in-game map is a navigational artifact, not a separate strategic movement layer.

### Generation

The base geography is largely hand-authored, but runtime state is heavily variable.

* Loot distribution is randomized.
* Zombie population varies spatially and migrates over time.
* Building states can vary through alarms, burned structures, boarded windows, survivor houses, vehicle conditions, road events, and meta-events.
* Power and water failure alter the world over time.

### Navigation and Scale

Movement is a major survival constraint.

* Long trips require planning around fuel, vehicle condition, exhaustion, noise, daylight, and road blockages.
* The same town feels different depending on zombie density, weather, alarms, and player-created noise.
* The player expands influence block by block rather than hopping between discrete sites.

### Simulation Layer

Project Zomboid translates CDDA-like survival pressure into a real-time seamless world.

* Sound propagation attracts zombies.
* Fire can spread.
* Visibility, weather, darkness, and interiors shape risk.
* Vehicles, injuries, hunger, thirst, boredom, panic, stress, infection, clothing, and temperature all interact with travel.

### Core Gameplay Loop

Spawn locally -> secure immediate shelter -> scavenge nearby houses -> establish storage and safety -> extend route network -> acquire and maintain vehicles -> manage long-term degradation, winter, and population pressure.

### Design Lesson

Project Zomboid proves that CDDA-like map pressure does not require a formal overmap. A seamless world can create similar decisions if distance, noise, and logistics remain punishing.

---

## UnReal World

### Map Architecture

UnReal World uses a large wilderness map with local zoomed-in detail.

* The macro layer represents forests, lakes, rivers, villages, marshes, hills, and coastlines.
* The player can zoom into a local tile-based area for precise actions such as building, hunting, trapping, combat, and crafting.
* The wilderness map is not just a travel board; it is the primary survival surface.

### Generation

Terrain, villages, cultures, resources, animals, and seasonal conditions are generated according to realistic environmental rules.

### Navigation and Scale

Travel consumes meaningful time and energy. Snow, ice, water, weather, darkness, injuries, fatigue, and load all influence movement.

Example: A winter route across forest and frozen lakes may be faster than summer travel in some areas, but the warmth and food risks are severe.

### Simulation Layer

The simulation emphasizes human-scale survival.

* Nutrition, warmth, fatigue, injury, skills, weather, and seasonal cycles matter.
* Hunting depends on tracks, terrain, stealth, weapon choice, fatigue, and animal behavior.
* Building and crafting are tied directly to local materials.

### Core Gameplay Loop

Travel wilderness -> identify resources or settlements -> zoom in for local survival actions -> hunt, build, trade, craft, trap, or fight -> survive across seasons.

### Design Lesson

UnReal World is CDDA-like through **ecological realism** rather than urban loot density.

---

## NEO Scavenger

### Map Architecture

NEO Scavenger uses a single hex world map.

* Hexes represent terrain, ruins, landmarks, and route options.
* The map handles both macro travel and many encounter contexts.
* Specific sites and encounters can trigger detailed interfaces rather than fully simulated local maps.

### Generation

The world combines fixed locations with randomized scavenging, combat, and events.

* Terrain influences visibility, movement, encounters, and scavenging quality.
* Daylight, weather, elevation, concealment, and character condition alter map decisions.

### Navigation and Scale

The player moves hex by hex, with limited action points. The question is often whether to spend time moving, hiding, scavenging, resting, tracking, or retreating.

### Simulation Layer

NEO Scavenger focuses on **stat-to-map coupling**.

* Hunger, thirst, warmth, sleep, injury, disease, burden, footwear, and concealment shape viable routes.
* Encounters resolve through character capabilities and inventory choices.
* Inventory itself is spatial: containers inside containers, limited carrying capacity, and awkward item dimensions affect survival.

### Core Gameplay Loop

Move hex -> manage exposure and visibility -> scavenge/fight/avoid -> adjust inventory and clothing -> seek fixed objectives -> repeat.

### Design Lesson

NEO Scavenger shows that a game can feel map-driven with a relatively abstract map if resource pressure and encounter rules are tightly coupled to terrain.

---

## RimWorld

### Map Architecture

RimWorld has a dual-scale structure, but with a different emphasis from CDDA.

* **World map**: A planet surface divided into tiles with biomes, terrain difficulty, roads, rivers, settlements, faction bases, quest sites, ancient complexes, and temporary events.
* **Colony map**: A local square tile map where the colony, pawns, buildings, animals, plants, fire, temperature, pathfinding, and combat are simulated.
* **Temporary generated maps**: Raids, quests, ambushes, caravans, ancient complexes, and mining sites can instantiate local maps separate from the main colony.

Caravans are the bridge between the two layers: pawns leave the local colony map and become a moving object on the world map, carrying goods, animals, prisoners, and supplies. RimWorld’s own wiki describes caravans as groups that leave the current map tile and are represented on the world map. 

### Generation

* The planet surface is generated at game start.
* The starting colony map is generated from world tile properties: biome, rainfall, temperature, elevation, stone types, caves, rivers, roads, pollution, and other parameters.
* Events generate temporary map sites and encounters.
* Faction settlements and quest sites create strategic destinations.

### Navigation and Scale

World travel is slower and more abstract than CDDA vehicle travel.

* Caravan speed depends on terrain, roads, animals, load, health, weather, and supplies.
* Long-distance movement is a strategic risk because colonists are absent from the base and can be ambushed, starve, freeze, or become ill.
* Drop pods, transport shuttles, farskip effects, and quests can change travel economics.

### Simulation Layer

RimWorld’s primary simulation density is local colony management.

* Pawns have needs, skills, health conditions, relationships, thoughts, ideology, genes, duties, equipment, and schedules.
* Rooms, temperature, beauty, cleanliness, light, cover, crops, animals, and power networks are map systems.
* Fire, infestations, raids, sieges, toxic fallout, mech clusters, and disease alter the colony’s spatial priorities.

### Core Gameplay Loop

Select world tile -> build and defend local colony -> respond to map events -> send caravans or pods to trade/quest/raid -> import resources and knowledge -> expand or relocate.

### Design Lesson

RimWorld is CDDA-like in its macro/local split but colony-centered rather than wanderer-centered. The map creates **logistics and opportunity cost**: every expedition removes labor and defense from the home site.

---

## Battle Brothers

### Map Architecture

Battle Brothers uses a procedural strategic world map plus separate tactical battlefields.

* **World map**: A generated continent with settlements, roads, terrain, faction territories, hostile camps, roaming parties, contracts, trade goods, and ambitions.
* **Tactical map**: When combat begins, the game switches to a turn-based hex battlefield.
* **Settlement layer**: Towns and castles expose markets, recruits, contracts, repair, healing, temples, training, and rumors.

Developer material describes the world map as procedurally generated for each new game, and combat as a switch from the world map to a tactical combat map with generated terrain.

### Generation

* World geography and settlement placement are generated at campaign start.
* Contracts, enemy parties, camps, crises, and market prices create changing strategic texture.
* Tactical battlefields are generated from terrain context and encounter type.

### Navigation and Scale

The company moves continuously across the world map.

* Terrain affects speed and visibility.
* Roads improve travel.
* Forests, mountains, snow, night, and hostile territory raise risk.
* Contracts create route planning problems: escort caravans, hunt beasts, destroy camps, retrieve artifacts, patrol roads, or deliver cargo.

### Simulation Layer

Battle Brothers abstracts survival more than CDDA but simulates mercenary-company logistics.

* Men have injuries, fatigue, morale, traits, wages, equipment durability, ammunition, food, medicine, tools, and experience.
* Settlements have prices, available recruits, contracts, modifiers, and faction relationships.
* The campaign economy pushes the player across the map.

### Core Gameplay Loop

Read contracts and rumors -> plot route -> intercept enemies or visit site -> resolve tactical combat -> repair/heal/pay wages -> exploit trade or faction opportunities -> repeat.

### Design Lesson

Battle Brothers is a strong example of **strategic-map pressure feeding tactical-map resolution**. Its world map is not a passive menu; it is an economic and risk-management layer.

---

## Starsector

### Map Architecture

Starsector translates the CDDA-like macro/local split into space.

* **Sector map**: A generated campaign space containing core systems, hyperspace, fringe systems, jump points, planets, stations, fleets, ruins, gates, and hyperspace storms.
* **System maps**: Individual star systems contain planets, asteroid belts, stations, fleets, gravity wells, sensor contacts, and salvage.
* **Combat maps**: Fleet battles resolve on separate tactical 2D maps.

The Starsector wiki describes hyperspace as the means of interstellar travel and the Sector Map as displaying the generated Sector for the current playthrough.

### Generation

* The sector includes a stable core plus generated fringe exploration content.
* Derelicts, ruins, probes, remnant systems, pirate bases, colonies, bounties, and exploration targets create map-driven objectives.
* Economy and faction activity generate fleet movements and market opportunities.

### Navigation and Scale

Travel is its own strategic game.

* Fuel, supplies, crew, cargo capacity, sensor profile, burn speed, storms, terrain, jump points, and hostile fleets constrain movement.
* Hyperspace is a dangerous transit layer rather than a simple fast-travel screen.
* The player must choose between stealth, speed, cargo efficiency, and combat readiness.

### Simulation Layer

Starsector’s simulation is fleet- and economy-oriented.

* Ships have combat readiness, fuel use, supply maintenance, cargo capacity, weapons, officers, hullmods, and damage.
* Markets have shortages, surpluses, stability, faction control, and trade restrictions.
* Colonies can be founded and defended, turning the map into a strategic ownership layer.

### Core Gameplay Loop

Scan intel -> plan route through hyperspace and systems -> explore/trade/smuggle/bounty/salvage -> fight or evade fleets -> refit and resupply -> invest in colonies or reputation -> repeat.

### Design Lesson

Starsector is CDDA-like in the sense that **logistics defines reach**. Fuel and supplies replace hunger and thirst; sensor range replaces line of sight; hyperspace storms replace dangerous terrain.

---

## Kenshi

### Map Architecture

Kenshi uses a huge seamless open world rather than a formal overmap/local split.

* The player can control one character or a squad across a continuous terrain.
* Towns, ruins, faction areas, biomes, roads, mines, shops, and bases exist in the same world.
* There is no discrete battle transition; combat and travel happen in place.

Kenshi’s official and wiki descriptions emphasize its open-ended, squad-based, free-roaming sandbox structure.

### Generation

Kenshi is not primarily procedural in the same way as CDDA. Its geography is authored, but its state is systemic.

* Faction patrols, wildlife, bandit groups, slavers, caravans, guards, shops, prisoners, hunger, injuries, and local conflicts generate emergent situations.
* Town states and world-state changes can alter locations after key NPCs are killed or captured.
* Player bases create new simulation centers.

### Navigation and Scale

Distance is significant because the world is physically traversed.

* Squad speed, athletics, encumbrance, injuries, prosthetics, hunger, stealth, and terrain affect movement.
* Travel through hostile zones can result in enslavement, limb loss, imprisonment, starvation, or recruitment opportunities.
* Multiple squads can operate in different locations.

### Simulation Layer

Kenshi’s map simulation is character- and faction-centered.

* Characters have body-part injuries, hunger, skills, jobs, inventories, faction relations, and AI schedules.
* Settlements and factions create local order.
* Player bases attract raids, traders, tax collectors, prayer days, bandits, and faction demands.

### Core Gameplay Loop

Choose route or settlement -> travel physically -> scavenge, mine, trade, steal, fight, or recruit -> recover and train -> build base or join conflicts -> reshape local faction state.

### Design Lesson

Kenshi is an example of **seamless systemic geography**: local and strategic choices occur on the same map, with no explicit transition layer.

---

## Minecraft

### Map Architecture

Minecraft uses a seamless chunked voxel world.

* The world is divided into chunks.
* Chunks stream around the player and are generated as needed.
* Vertical space is fully structural: caves, mountains, oceans, mineshafts, strongholds, villages, and player builds share the same coordinate system.

### Generation

* Terrain, biomes, caves, ores, structures, villages, dungeons, vegetation, and mobs are generated from world seed and local rules.
* New chunks are generated lazily when first explored.
* Player changes persist in loaded/generated chunks.

### Navigation and Scale

Minecraft has no built-in strategic overmap equivalent to CDDA’s overmap. The player builds their own navigation layer through maps, landmarks, roads, Nether routes, coordinates, boats, rails, horses, elytra, and portals.

### Simulation Layer

The local world is highly manipulable.

* Blocks are both terrain and resources.
* Light level, fluids, redstone, mob spawning, crop growth, fire, weather, portals, and block updates create systemic behavior.
* Chunk loading boundaries affect farms, machines, mob systems, and travel infrastructure.

### Core Gameplay Loop

Explore terrain -> mine/scavenge resources -> craft tools and infrastructure -> build bases and routes -> push to new biomes/structures/dimensions -> automate or decorate -> repeat.

### Design Lesson

Minecraft shows a different answer to the same problem: instead of a semantic overmap that creates local detail, it creates **continuous local detail everywhere** and lets the player invent strategic abstraction.

---

## Factorio

### Map Architecture

Factorio uses an effectively unbounded, chunked, top-down world.

* Terrain, resources, water, trees, cliffs, enemy nests, and pollution all exist on one continuous surface.
* The player can zoom out and use map/radar views, but the world remains a single simulation space.
* Radar coverage creates an information layer comparable to scouting.

### Generation

* Resource patches, terrain, water, enemy bases, and forests are generated by seed and map settings.
* New chunks are generated as the explored frontier expands.
* Enemy expansion and pollution response create dynamic pressure.

### Navigation and Scale

Factorio’s travel evolves.

* Early travel is walking through local terrain.
* Midgame uses vehicles, trains, roads, and radar.
* Lategame logistics can include rail networks, construction robots, artillery, and remote map interaction.

### Simulation Layer

The simulation is industrial rather than survivalist.

* Belts, inserters, machines, fluids, power grids, trains, robots, pollution, biters, logistics networks, and resource depletion are map-bound systems.
* Pollution spreads spatially and provokes enemy attacks.
* Throughput and distance become design constraints.

### Core Gameplay Loop

Find resources -> build extraction and production -> defend and expand -> automate logistics -> claim new resource patches -> scale factory -> launch and optimize.

### Design Lesson

Factorio is a non-survival cousin of CDDA-like maps: its map pressure comes from **resource geography and logistics**, not hunger or scavenging.

---

## The Long Dark

### Map Architecture

The Long Dark uses a network of handcrafted survival regions.

* Each region is a large traversable local map with shelters, caves, roads, rivers, railways, cabins, industrial sites, wildlife zones, and transition points.
* The world map is not a procedural overmap, but the player gradually builds mental and in-game cartographic knowledge.
* Regions connect into a broader route network.

### Generation

The world is mostly fixed, but loot, wildlife, weather, and certain spawn conditions vary.

### Navigation and Scale

Navigation is central.

* Weather, visibility, temperature, fatigue, injuries, predators, thin ice, rope climbs, and carrying capacity make route choice meaningful.
* Long trips require staged supplies, shelter knowledge, and daylight planning.
* Mapping is experiential: landmarks, roads, railways, cave systems, and shortcuts matter.

### Simulation Layer

The survival model is focused and legible.

* Warmth, fatigue, hunger, thirst, condition, clothing, fire, wind exposure, food decay, and injury shape movement.
* Wildlife movement and weather create changing local risk.

### Core Gameplay Loop

Leave shelter -> navigate under weather and temperature pressure -> scavenge/hunt/repair -> return or push to next shelter -> cache supplies -> learn regional routes -> survive longer.

### Design Lesson

The Long Dark is not procedural in the CDDA sense, but it is highly relevant as a study in **map knowledge as survival progression**.

---

## Sunless Sea / Sunless Skies

### Map Architecture

Sunless Sea and Sunless Skies use large overworld maps built around travel, discovery, ports, and resource pressure.

* The player moves a vessel through a dangerous navigation layer.
* Ports, islands, stations, monsters, hazards, and story sites serve as encounter nodes.
* Local detail is mostly textual/event-based rather than tile-simulated.

### Generation

* The map layout can be partly randomized between playthroughs.
* Ports and major story locations contain authored narrative content.
* Events and resource pressure emerge during travel.

### Navigation and Scale

The map itself is dangerous.

* Fuel, supplies, terror, hull condition, crew, light, enemies, and route length shape exploration.
* Known ports become logistical anchors.
* The player gradually converts an unknown sea/sky into a trade and survival network.

### Simulation Layer

Simulation is abstract but effective.

* Resource decay during travel forces route planning.
* Terror accumulates with darkness and distance.
* Combat and story events interrupt travel.

### Core Gameplay Loop

Leave port -> explore unknown waters/skies -> manage fuel/supplies/terror -> discover port or hazard -> trade, repair, recruit, or complete storylet -> return with knowledge and cargo.

### Design Lesson

These games show how a map can become compelling with **resource attrition plus narrative nodes**, even without a dense local tile layer.

---

## Roadwarden

### Map Architecture

Roadwarden is a narrative RPG built around a regional route map.

* Locations are nodes connected by paths.
* Travel time, danger, daylight, supplies, and knowledge shape route selection.
* Local interactions are primarily text-driven.

### Generation

The world is mostly authored, but the player’s state, timing, choices, relationships, and accumulated knowledge change how map nodes function.

### Navigation and Scale

The map creates a daily planning problem.

* Travel consumes time.
* Some roads are unsafe or blocked until explored, repaired, negotiated, or understood.
* The player learns which routes are efficient and which locations can provide shelter, trade, or information.

### Simulation Layer

Roadwarden abstracts survival into limited resources and consequences.

* Food, health, armor, coins, reputation, time, and information define reach.
* Social state is part of map state: a village, inn, tribe, or ruin changes because of relationships and discoveries.

### Core Gameplay Loop

Select route -> spend daylight and resources -> investigate or negotiate at location -> update knowledge and relationships -> return, rest, or push onward.

### Design Lesson

Roadwarden is useful context because it strips the CDDA-like map loop down to **route planning, scarcity, and changing location state**.

---

## King of Dragon Pass / Six Ages

### Map Architecture

These games use a clan territory map and expedition layer rather than a tactical grid.

* The player manages a settlement/clan.
* Expeditions travel across a regional map to explore, raid, trade, negotiate, quest, or interact with spirits and neighbors.
* Location knowledge expands through scouting and events.

### Generation

* Events are selected from large authored pools with stateful conditions.
* Neighboring clans, resources, threats, myths, diplomacy, and exploration results create campaign texture.

### Navigation and Scale

The player does not walk tile by tile. Instead, the map is a strategic and social surface.

* Expeditions consume people, time, goods, animals, and political opportunity.
* The question is not “what is on this exact tile?” but “what do we risk by sending people there now?”

### Simulation Layer

The simulation is social, mythic, and economic.

* Clan mood, food, cattle, magic, reputation, diplomacy, leadership, war, and ritual knowledge affect outcomes.
* Map choices feed into social consequences.

### Core Gameplay Loop

Allocate clan resources -> send explorers/traders/raiders/diplomats -> resolve event or discovery -> adjust politics, food, cattle, and magic -> plan next season.

### Design Lesson

These games demonstrate a **non-spatially dense but highly stateful campaign map**. They are useful when thinking about CDDA-like systems at the faction or community scale.

---

## Daggerfall

### Map Architecture

The Elder Scrolls II: Daggerfall uses a huge regional map with towns, dungeons, temples, guilds, wilderness, and fast travel.

* The macro map is enormous and strategic.
* Local towns and dungeons instantiate as navigable spaces.
* Wilderness scale is vast, but much of the meaningful content is accessed through travel and site entry.

### Generation

* The world uses large-scale procedural methods and repeated templates.
* Dungeons can be sprawling generated structures.
* Towns, services, factions, and quests create distributed destinations.

### Navigation and Scale

Daggerfall is relevant because it separates **geographic scale** from **content density**.

* Fast travel is essential.
* Route choice can involve time, cost, risk, and travel mode.
* The macro world communicates vastness more than moment-to-moment survival pressure.

### Simulation Layer

The simulation is RPG-oriented.

* Factions, reputation, legal status, time limits, diseases, inventory, spells, and dungeons shape travel decisions.
* Local dungeon navigation can be complex and disorienting.

### Core Gameplay Loop

Take quest -> travel to city/dungeon/site -> navigate local space -> fight, loot, retrieve, or interact -> return before deadline -> manage faction and character progression.

### Design Lesson

Daggerfall is a useful caution: huge procedural maps need strong local generation, travel costs, and information systems or they risk feeling repetitive.

---

## Ultima Ratio Regum

### Map Architecture

Ultima Ratio Regum is an experimental procedural world project focused on culture, history, geography, symbols, religions, nations, cities, and artifacts.

* The world map encodes civilizations, borders, climates, resources, and settlements.
* Local spaces are generated with cultural and symbolic specificity.
* The map is a representation of generated anthropology as much as geography.

### Generation

* Procedural cultures, flags, religions, architecture, books, histories, and political entities are central.
* The goal is not just terrain variety but interpretive depth.

### Navigation and Scale

URR is useful as a design reference for maps where exploration means **decoding culture**.

* Location context affects architecture, iconography, language, religion, and artifacts.
* Discovery is informational, not only material.

### Simulation Layer

The simulation emphasis is semiotic and historical rather than survivalist.

* Symbols and generated cultural rules make places legible as products of their societies.
* The map becomes a research surface.

### Core Gameplay Loop

Explore region -> enter settlement/site -> infer culture and history from generated details -> gather information -> pursue broader investigative goals.

### Design Lesson

URR extends Qud and Dwarf Fortress in a more cultural direction: a map can generate meaning through procedural signs, not only loot and monsters.

---

## Shadow Empire

### Map Architecture

Shadow Empire is a 4X/wargame with a procedural planet map.

* Hexes encode terrain, climate, roads, ruins, resources, zones, logistics, and military positions.
* Settlements and zones form administrative centers.
* Military fronts, supply routes, and infrastructure are spatially explicit.

### Generation

* The planet is procedurally generated with geology, climate, hydrology, population remnants, resources, and political starting conditions.
* Strategic problems emerge from terrain, distance, logistics, and neighbor placement.

### Navigation and Scale

Movement is operational rather than personal.

* Roads, rail, truck logistics, terrain, supply bases, and administrative range decide what can be held.
* The map is a logistical constraint system.

### Simulation Layer

Simulation is state-level.

* Population, industry, food, water, metal, oil, logistics, politics, units, leaders, and organizations interact.
* Hex control and supply lines are decisive.

### Core Gameplay Loop

Survey map -> expand zones and infrastructure -> secure resources -> project logistics -> fight wars -> integrate territory -> repeat.

### Design Lesson

Shadow Empire is a useful non-survival comparison because it shows CDDA-like principles scaled up to governance: **the map is a logistics machine**.

---

## Rain World

### Map Architecture

Rain World uses a fixed but highly systemic 2D region graph.

* Rooms connect into regions.
* The player learns routes through shelters, gates, pipes, predator territories, scavenger zones, and food sources.
* The map is not procedural, but it behaves like an ecology.

### Generation

The geography is authored. The dynamic element is creature movement, weather cycle, and systemic interaction.

### Navigation and Scale

Travel is constrained by the rain cycle.

* Shelters create route checkpoints.
* The player must decide how far to forage before returning.
* Predator behavior, water, verticality, pipes, and region transitions produce spatial pressure.

### Simulation Layer

Rain World’s simulation is ecological.

* Creatures have behaviors, territories, relationships, prey/predator dynamics, and persistence-like continuity.
* The player is one organism in a hostile food web.

### Core Gameplay Loop

Leave shelter -> forage and navigate -> avoid or exploit creatures -> reach next shelter before rain -> learn route network -> migrate between regions.

### Design Lesson

Rain World is CDDA-adjacent because it shows that **ecological pressure plus route learning** can create survival-map gameplay without procedural generation.

---

## Noita

### Map Architecture

Noita uses a continuous 2D pixel-simulated world with biome layers.

* The world is spatially continuous.
* Biomes and special regions provide macro structure.
* Local pixels are physically reactive materials.

### Generation

* World layout, biome content, enemies, materials, and items are procedurally generated.
* The player’s spells can radically alter terrain.

### Navigation and Scale

Movement is local and hazardous.

* The player digs, burns, swims, levitates, teleports, or blasts through the world.
* Route choice is shaped by material physics and enemy danger, not an overmap.

### Simulation Layer

Noita is defined by per-pixel simulation.

* Liquids, gases, powders, fire, electricity, explosions, toxic sludge, polymorph, and magical effects interact locally.
* The map is destructible and reactive.

### Core Gameplay Loop

Enter biome -> explore for wands/spells/gold -> survive material hazards and enemies -> alter terrain -> descend or branch -> combine spells -> repeat.

### Design Lesson

Noita is not CDDA-like structurally, but it is highly relevant as an extreme example of **map-as-simulation substrate**.

---

## Spelunky / Spelunky 2

### Map Architecture

Spelunky uses discrete procedurally generated levels rather than a persistent world map.

* Each level is a compact tile space.
* Biomes provide macro progression.
* Special entrances, shortcuts, shops, altars, and secrets create route structure.

### Generation

* Levels are assembled from authored chunks, rules, enemy/item placement, and special cases.
* Generation produces readable but surprising tactical maps.

### Navigation and Scale

The level is short-lived but dense.

* Time pressure, traps, enemies, bombs, ropes, shops, sacrifice mechanics, mounts, and liquid physics make each screen tactically rich.
* The player learns generation grammar over repeated runs.

### Simulation Layer

* Local interactions are high-density: falling objects, explosions, liquids, shopkeeper behavior, enemy interactions, mounts, traps, and item synergies.
* Persistence is run-level rather than world-level.

### Core Gameplay Loop

Read generated room grammar -> navigate hazards -> conserve bombs/ropes/health -> exploit or avoid systems -> descend -> repeat.

### Design Lesson

Spelunky is useful because it demonstrates **procedural readability**. Even if the world is not persistent, local map grammar teaches the player to reason under uncertainty.

---

## Arma / DayZ / Survival Sandbox Lineage

### Map Architecture

DayZ and related survival sandboxes use large, mostly handcrafted continuous maps.

* Towns, military bases, forests, roads, rivers, airfields, and coastlines form strategic geography.
* There is no formal overmap layer; external or in-game maps support navigation.
* Travel happens at full local scale.

### Generation

* Geography is authored.
* Loot, player encounters, infected populations, server persistence, weather, and vehicle states vary.

### Navigation and Scale

The map creates social and logistical survival.

* Food, water, disease, ammunition, noise, visibility, and player threat affect route planning.
* Known landmarks, road signs, power lines, coastlines, and terrain recognition become survival skills.

### Simulation Layer

The strongest system is multiplayer uncertainty.

* Other players, bases, stashes, vehicles, shots, traps, and contested loot make geography socially dangerous.
* Persistence varies by server rules.

### Core Gameplay Loop

Spawn with little -> navigate by landmarks -> scavenge low-risk zones -> move inland or toward military sites -> avoid or engage players -> build/stash/repair -> repeat after death.

### Design Lesson

This lineage shows a non-procedural route to CDDA-like tension: **human uncertainty can replace procedural uncertainty**.

---

## Tabletop Hexcrawls

### Map Architecture

A classic hexcrawl uses a macro hex map with local encounter resolution.

* Each hex has terrain, travel cost, keyed locations, random encounter tables, and sometimes hidden features.
* Local sites use theater of the mind, dungeon maps, pointcrawls, or battle grids.

### Generation

* The referee may pre-key hexes, roll content as needed, or combine both.
* Random encounter tables, weather tables, reaction rolls, stocking tables, and resource checks produce emergent travel.

### Navigation and Scale

Time and roles matter.

* Parties choose pace, direction, watches, foraging, scouting, navigation method, and camp procedure.
* Getting lost, weather, darkness, river crossings, and pursuit create consequences.

### Simulation Layer

A good hexcrawl does not need dense per-tile simulation. It needs strong procedures.

* Rations, torches, ammunition, mounts, hirelings, morale, disease, fatigue, and encumbrance create travel friction.
* Factions and wandering monsters make the wilderness active.

### Core Gameplay Loop

Choose route -> spend travel turn/watch/day -> check navigation/weather/encounters/resources -> discover or miss content -> resolve local site -> return to safety or camp.

### Design Lesson

Hexcrawls are the analog ancestor of many CDDA-like structures. They demonstrate that **procedural travel rules** can be more important than graphical fidelity.

---

## Pointcrawls

### Map Architecture

A pointcrawl abstracts space into nodes and routes.

* Nodes are meaningful locations.
* Edges are paths with travel times, risks, costs, or conditions.
* The map does not need to represent every meter of terrain.

### Generation

Pointcrawls can be authored, randomly generated, or dynamically expanded.

### Navigation and Scale

The player chooses routes rather than coordinates.

* This is useful when terrain detail is less important than connection structure.
* Roads, tunnels, ferry routes, mountain passes, ley lines, trade lanes, sewer networks, and social connections can all be pointcrawl edges.

### Simulation Layer

* Route properties carry the systemic load: danger, tolls, weather exposure, travel time, encounter chance, stealth, capacity, or faction control.
* Nodes store state: supplies, allies, enemies, rumors, safe beds, markets, repairs.

### Core Gameplay Loop

Pick destination -> choose edge -> pay time/risk/resource cost -> resolve event -> update node state -> choose next route.

### Design Lesson

Pointcrawls are useful for digital design when a full local map would be expensive or unnecessary. They preserve map-driven choice while lowering spatial complexity.

---

## GIS Tile Pyramids and Slippy Maps

### System Type

Real-world digital mapping systems such as web maps are not games, but they solve many related technical problems.

### Map Architecture

* The world is divided into tiles at multiple zoom levels.
* Higher zoom levels provide more local detail.
* Tiles are streamed and cached based on viewport.
* Layers can include roads, terrain, satellite imagery, transit, buildings, traffic, labels, weather, and boundaries.

### Generation and Data

Instead of procedural fantasy generation, GIS maps use data pipelines.

* Vector tiles, raster tiles, elevation models, routing graphs, labels, and metadata are transformed into renderable layers.
* Different layers appear at different zoom levels.
* Caching and incremental loading are core concerns.

### Navigation and Scale

Users constantly move between macro and micro perspectives.

* Continental view -> city view -> street view -> building-level detail.
* Routing engines compute travel time, constraints, and alternatives.

### Simulation Layer

Some layers are dynamic.

* Traffic, transit, weather, hazards, closures, wildfire spread, flood maps, and population flows can update over time.

### Design Lesson

GIS systems are the non-game version of an overmap/local architecture. They show the value of **level-of-detail, streaming, semantic layers, and zoom-dependent information density**.

---

## Logistics Networks and Supply-Chain Models

### System Type

Supply-chain planning, military logistics, emergency response, and infrastructure simulation use map systems that resemble strategic survival games.

### Map Architecture

* Nodes: warehouses, cities, bases, ports, hospitals, depots, factories.
* Edges: roads, rail, shipping lanes, air routes, pipelines, power lines, data links.
* Regions: demand zones, territories, hazard zones, service areas.

### Generation and Data

These systems may use real data, forecasts, optimization models, or simulated disruptions.

### Navigation and Scale

The core question is reach under constraint.

* How much can be moved?
* How quickly?
* Through which route?
* With what risk?
* What breaks if a node or edge fails?

### Simulation Layer

* Inventory, fuel, staffing, demand, congestion, breakdowns, weather, attacks, regulations, and maintenance create map pressure.

### Core Loop

Assess demand -> allocate capacity -> route resources -> respond to disruption -> update network -> repeat.

### Design Lesson

This is CDDA-like at an institutional scale. Survival games ask whether one character can reach food; logistics systems ask whether an organization can keep a population supplied.

---

## Comparative Taxonomy

| System | Spatial Model | Generation Style | Persistence | Simulation Focus | Closest CDDA Analogy |
| --- | --- | --- | --- | --- | --- |
| **CDDA** | Overmap + local tiles + Z | Lazy JSON/data mapgen | High tile/site/world persistence | Items, monsters, vehicles, fields, survival | Baseline |
| **Caves of Qud** | World map + local zones | Fixed skeleton + procedural histories | Medium-high | Factions, lore, mutations, liquids | Overmap POIs with generated identity |
| **Dwarf Fortress Adventure** | World + sites + history | Heavy upfront worldgen | Very high | Creature/history/social simulation | World state behind local maps |
| **Project Zomboid** | Seamless chunked world | Fixed geography + random states | High | Zombies, sound, fire, survival | CDDA without overmap fast-travel |
| **UnReal World** | Wilderness map + local zoom | Procedural ecology | Medium-high | Weather, seasons, realistic survival | Rural survival overmap |
| **NEO Scavenger** | Single hex map | Fixed sites + random encounters | Medium | Stats, inventory, exposure | Abstracted CDDA travel |
| **RimWorld** | Planet map + colony maps | Generated planet/local maps + events | High local, medium global | Colony, pawns, raids, caravans | Base-centered CDDA |
| **Battle Brothers** | Strategic world + tactical hex battles | Procedural campaign + battlefields | Medium | Company logistics and tactical combat | Mercenary overmap with encounter maps |
| **Starsector** | Sector/system maps + combat maps | Generated fringe + dynamic economy | Medium-high | Fleet logistics, economy, colonies | Space CDDA logistics |
| **Kenshi** | Seamless open world | Authored geography + systemic state | Medium-high | Squads, factions, injuries, bases | Seamless CDDA-like sandbox |
| **Minecraft** | Seamless voxel chunks | Lazy seed chunks | High chunk persistence | Blocks, crafting, mobs, building | Infinite local map |
| **Factorio** | Seamless generated chunks | Seed terrain/resources/enemies | High | Logistics, pollution, automation | Industrial survival map |
| **The Long Dark** | Handcrafted region network | Fixed regions + variable states | Medium | Weather, warmth, route knowledge | Authored survival hexcrawl |
| **Sunless Sea/Skies** | Overworld node/region map | Semi-random layout + authored ports | Medium | Fuel, supplies, terror, story | Narrative resource overmap |
| **Roadwarden** | Node/route map | Authored with stateful change | Medium | Time, safety, social knowledge | Textual pointcrawl CDDA |
| **King of Dragon Pass / Six Ages** | Clan territory expedition map | Authored event pools + state | Medium-high | Clan economy, myth, diplomacy | Community-scale overmap |
| **Daggerfall** | Huge world + local towns/dungeons | Large procedural/template systems | Medium | RPG quests, factions, time | Macro scale without survival density |
| **Ultima Ratio Regum** | Cultural world + local sites | Procedural culture/history | Medium | Semiotics, cultures, artifacts | Procedural meaning map |
| **Shadow Empire** | Planetary hex strategy map | Procedural planet + factions | High | Logistics, zones, war, governance | CDDA logistics scaled to states |
| **Rain World** | Fixed region graph/local rooms | Authored ecology | Medium | Creature ecology, route pressure | Ecological route survival |
| **Noita** | Continuous pixel world | Procedural biomes | Run persistence | Material physics | Local simulation substrate |
| **Spelunky** | Procedural discrete levels | Chunk/rule levelgen | Low per run | Tactical hazard grammar | Readable procedural local maps |
| **DayZ/Arma survival** | Large seamless authored map | Fixed terrain + variable loot/players | Server-dependent | Social threat, navigation, scarcity | Multiplayer route survival |
| **Tabletop Hexcrawl** | Hex map + local encounters | Keyed + tables | Referee-dependent | Travel procedure, resources | Analog overmap ancestor |
| **Pointcrawl** | Nodes + routes | Authored/procedural hybrid | Referee/system-dependent | Routes, costs, node state | Abstract overmap |
| **GIS/slippy maps** | Multi-zoom tiled map | Data pipelines | External/dynamic | Layers, routing, traffic | Non-game overmap/local LOD |
| **Supply-chain models** | Nodes/edges/regions | Data/simulation/optimization | High | Capacity, routes, disruption | Institutional survival logistics |

---

## Pattern Library

### Pattern 1: Semantic Macro Tile -> Local Generator

A macro tile stores a compact semantic type: `hospital`, `forest`, `lab`, `road`, `river`, `mine`, `town`, `ruin`.

When entered, a local generator expands that semantic type into:

* Geometry.
* Terrain and furniture.
* Loot tables.
* Enemy or NPC populations.
* Environmental hazards.
* Special cases.
* Persistent state.

Best examples: CDDA, Caves of Qud, Dwarf Fortress, RimWorld, Battle Brothers.

### Pattern 2: Seamless Chunk Streaming

The world is continuous, but internally divided into chunks.

Advantages:

* No hard transition between map scales.
* Player movement feels grounded.
* Local persistence is intuitive.
* Long-distance logistics can emerge from physical traversal.

Costs:

* More demanding streaming and persistence.
* Harder to provide strategic readability.
* Large worlds can become tedious without vehicles, fast travel, landmarks, or infrastructure.

Best examples: Project Zomboid, Kenshi, Minecraft, Factorio, DayZ.

### Pattern 3: Abstract Travel Layer + Encounter Resolution

The map is not locally simulated everywhere. Instead, it uses travel turns, encounter checks, and site interfaces.

Advantages:

* Efficient content production.
* Strong pacing.
* Easy to combine authored and random content.
* Good for narrative or tabletop systems.

Costs:

* Less local emergence.
* Repeated encounter templates can become visible.
* Player may feel detached from physical geography.

Best examples: NEO Scavenger, Sunless Sea, Roadwarden, tabletop hexcrawls, pointcrawls.

### Pattern 4: Worldgen Before Play

The system creates a world and then lets play occur inside that result.

Advantages:

* Strong global coherence.
* History and geography can influence each other.
* Generated worlds can be studied by the player.

Costs:

* Expensive generation.
* Harder to patch or alter after creation.
* The simulation may generate irrelevant detail.

Best examples: Dwarf Fortress, Caves of Qud, Shadow Empire, Daggerfall, Ultima Ratio Regum.

### Pattern 5: Handcrafted World + Procedural State

The geography is authored, but local conditions vary.

Advantages:

* Strong level design and landmarks.
* Replayability through state variation.
* Easier narrative placement.

Costs:

* Less geographic novelty after repeated play.
* Requires enough dynamic systems to avoid memorization.

Best examples: Project Zomboid, The Long Dark, Kenshi, Rain World, DayZ.

### Pattern 6: Resource Attrition as Map Engine

Travel consumes resources and creates pressure.

Typical resources:

* Food.
* Water.
* Warmth.
* Fuel.
* Ammunition.
* Medicine.
* Tools.
* Wages.
* Morale.
* Time.
* Visibility.
* Carrying capacity.
* Vehicle durability.
* Social permission.
* Reputation.

Best examples: CDDA, NEO Scavenger, UnReal World, Sunless Sea, Starsector, Battle Brothers, The Long Dark.

### Pattern 7: Map Knowledge as Progression

The player becomes stronger not only by leveling up but by knowing the world.

Knowledge includes:

* Safe routes.
* Dangerous zones.
* Loot-rich locations.
* Shelter locations.
* Seasonal crossings.
* Faction borders.
* Trade routes.
* Vehicle access.
* Shortcut networks.
* Weather patterns.
* Enemy migration paths.
* Hidden entrances.
* Reliable food/water sources.

Best examples: CDDA, Project Zomboid, The Long Dark, Rain World, Sunless Sea, Kenshi.

---

## Evaluation Rubric for the Target Solution

Use this rubric to separate full architectural candidates from examples that only contribute one useful pattern.

| Question | Strong Answer | Weak Answer |
| --- | --- | --- |
| Is the map at player scale? | The player moves through concrete local terrain and objects. | The player mostly selects nodes, missions, or destinations. |
| Does local state persist? | Looting, building, fire, corpses, damage, faction control, and routes can matter later. | Encounters disappear after resolution. |
| Is macro scale tied to local detail? | Strategic symbols generate or summarize actual local spaces. | Macro labels are disconnected from local play. |
| Does travel create decisions? | Terrain, time, supplies, vehicles, danger, and knowledge change route choice. | Travel is mostly a timer or loading screen. |
| Can the player build operational knowledge? | Safe routes, caches, bases, shortcuts, danger zones, and landmarks accumulate value. | Map knowledge has little long-term use. |
| Is Z-axis useful? | Vertical layers create tactical, navigational, and persistence problems. | Verticality is absent or cosmetic. |
| Is Z-axis required? | No. It is a desirable capability, not a gate. | Treating Z-axis as mandatory would exclude useful 2D persistence examples. |

## Recommended Architecture Direction

For a CDDA-like target, the strongest direction is a **persistent player-scale world with a strategic summarization layer**.

The strategic layer should answer high-level questions:

* What kind of place is this?
* What does the player know about it?
* How hard is it to reach?
* What major state has changed there?
* What routes, hazards, and resources are implied?

The local layer should answer concrete play questions:

* What tile, object, entity, or structure is here?
* What can the player see, hear, open, break, carry, repair, burn, climb, dig, loot, fortify, or avoid?
* What changed because of previous visits?
* What should be stored exactly, summarized, or regenerated deterministically?

Z-axis should be treated as an extensibility requirement where possible. The data model should not prevent multiple stacked local layers, even if early examples, prototypes, or reference games are mostly two-dimensional.

## Design Implications for a CDDA-like System

### 1. Decide Whether the Overmap Is Strategic, Diegetic, or Merely UI

An overmap can be:

* **Strategic**: Used for actual travel and route planning.
* **Diegetic**: Represents what the character knows or has mapped.
* **Administrative**: Used by the engine for generation and persistence.
* **UI-only**: A readable representation of the local world.

CDDA’s overmap is strategic and administrative. Project Zomboid’s in-game map is mostly diegetic/UI. Minecraft’s coordinate system and player-made maps are diegetic tools layered on a continuous world.

### 2. Make Macro Symbols Honest but Incomplete

A macro tile should tell the truth at the right resolution.

Good examples:

* “Hospital” tells the player to expect medical loot and dense urban danger, but not the exact room layout.
* “Forest” tells the player about movement, cover, and wood, but not every animal or cabin.
* “Lab” promises high-tech risk/reward, but local layout and threats remain uncertain.

The strategic layer should support planning without eliminating discovery.

### 3. Couple Travel Costs to Local Decisions

Travel should interact with:

* Inventory.
* Vehicle choice.
* Time of day.
* Weather.
* Route surfaces.
* Injuries.
* Companions.
* Noise.
* Light.
* Faction control.
* Food and fuel.

The more travel consumes local resources, the more the macro map matters.

### 4. Let Local Events Rewrite the Macro Map

A strong world remembers local events at higher scales.

Examples:

* A building burns down and the overmap marker changes.
* A road is blocked by wrecks or barricades.
* A faction captures a town.
* A refugee camp grows or collapses.
* A fungal or zombie infestation spreads.
* A player base becomes a known trade hub or raid target.
* A bridge collapses and changes route planning.

### 5. Use Multiple Densities of Simulation

A persistent player-scale map does not require every tile, object, and creature to run at full fidelity all the time. The important requirement is that the player’s meaningful changes survive unloading and that distant summaries can expand back into believable local state.

Not every region needs full CDDA-level detail all the time.

Possible layers:

* **Dormant summary state**: Distant town stores population, danger, loot depletion, faction, fire status.
* **Active abstract simulation**: Nearby offscreen hordes, fires, patrols, weather fronts, or caravans update at low resolution.
* **Loaded local simulation**: Full tile/entity update around player.
* **Historical event log**: Important changes are stored as events rather than continuous simulation.

This makes persistence feasible without simulating every tile every turn.

### 6. Design Mapgen Around Verbs

Locations should be generated around what players can do there.

Poor macro tile: `building`.

Better macro tile: `place where player can hide, loot medicine, attract zombies with alarms, climb to roof, salvage electronics, and risk infection`.

Useful verbs:

* Scout.
* Loot.
* Hide.
* Fortify.
* Burn.
* Flood.
* Dig.
* Climb.
* Trap.
* Trade.
* Ambush.
* Repair.
* Refuel.
* Hunt.
* Forage.
* Sleep.
* Signal.
* Recruit.
* Desecrate.
* Salvage.
* Evacuate.
* Cultivate.
* Survey.

### 7. Treat Transport as Character Progression

In CDDA-like systems, transport often matters as much as weapons.

Progression ladder examples:

* Walking.
* Backpacking.
* Bicycle.
* Shopping cart or sled.
* Horse or pack animal.
* Car.
* Armored vehicle.
* Boat.
* Train.
* Aircraft.
* Teleportation.
* Road network.
* Supply caches.
* Autonomous drones.
* Faction caravans.

Each transport mode changes the map’s topology by making some distances affordable and others impossible.

### 8. Store Persistence at the Right Resolution

Persistent player-scale maps need a save model that distinguishes between canonical generated content and player/world deltas.

Useful storage categories:

* **Seeded base generation**: Terrain, building shells, biome layout, road networks, and default object placement can often be reproduced from seed and versioned content rules.
* **Local deltas**: Broken doors, moved furniture, looted containers, dropped items, blood, fire damage, construction, traps, corpses, vehicle positions, and player caches usually need exact storage.
* **Site summaries**: Distant locations can store loot depletion, danger level, faction owner, fire status, infestation, population, known entrances, and major damage without simulating every object.
* **Event records**: Important events such as “bridge collapsed,” “lab breached,” “horde migrated,” or “base raided” can drive later regeneration and overmap presentation.
* **Vertical deltas**: If Z-axis exists, deltas need layer identity. A burned stairwell, collapsed floor, flooded basement, rooftop barricade, or breached tunnel must survive across vertical transitions.

The design goal is not maximum fidelity everywhere. It is **trustworthy continuity**: when the player returns, the world should preserve the consequences they reasonably expect to matter.

---

## Practical Design Matrix

Use this matrix when evaluating or designing a CDDA-like map system.

| Question | Low-Complexity Answer | High-Complexity Answer | Risk |
| --- | --- | --- | --- |
| How is space divided? | Nodes or hexes | Infinite tile/chunk world | High complexity may become unmanageable |
| When is content generated? | On encounter | At worldgen + lazy local generation | Upfront generation can waste detail |
| What persists? | Site flags | Individual tiles/items/entities | Persistence can bloat saves |
| What does travel cost? | Time only | Time, food, fuel, fatigue, weather, danger | Too much friction can feel tedious |
| How does the player learn the map? | Revealed nodes | Fog, scouting, rumors, sensors, landmarks | Too little knowledge feels random |
| How local is combat? | Abstract event | Full tactical simulation | Local detail can slow pacing |
| How does the world change? | Quest flags | Factions, fires, migrations, construction, ecology | Dynamic worlds need readable feedback |
| What makes routes different? | Distance | Terrain, safety, supplies, politics, vehicles | Complex routes need good UI |
| How do locations differ? | Loot tables | Layout, verbs, factions, hazards, history | Procedural variety can become noisy |
| What is the player’s long-term map goal? | Visit objectives | Build logistics network, bases, routes, allies | Open-ended maps need self-directed goals |

---

## Shortlist by Relevance to CDDA

### Closest Structural Relatives

* **Caves of Qud**: Dual-scale exploration with procedural sites and history.
* **Dwarf Fortress Adventure Mode**: Worldgen, history, and local simulation.
* **UnReal World**: Wilderness survival and zoomed local action.
* **RimWorld**: Planet/local map split and caravan logistics.
* **Battle Brothers**: Strategic procedural map feeding tactical encounters.

### Closest Survival-Pressure Relatives

* **Project Zomboid**: Seamless survival logistics, sound, vehicles, and local persistence.
* **NEO Scavenger**: Hex travel, scavenging, exposure, and inventory pressure.
* **The Long Dark**: Route planning, weather, warmth, and shelter knowledge.
* **DayZ**: Landmark navigation, scarcity, social threat, and route risk.
* **Sunless Sea**: Fuel/supply attrition and unknown-map exploration.

### Closest Simulation-Substrate Relatives

* **Minecraft**: Chunked world, persistent modification, local procedural generation.
* **Factorio**: Resource geography, pollution, logistics, and expansion.
* **Kenshi**: Seamless faction/squad simulation and base consequences.
* **Noita**: Dense local material simulation.
* **Rain World**: Ecology and route survival.

### Closest Analog/Non-Game Relatives

* **Tabletop hexcrawls**: Travel turns, encounter tables, resource depletion.
* **Pointcrawls**: Abstract route networks and node state.
* **GIS tile maps**: Multi-zoom, streamed, layered spatial data.
* **Supply-chain models**: Logistics, reach, capacity, disruption.
* **Military operational maps/wargames**: Terrain, supply, scouting, and force projection.

---

## Final Synthesis

CDDA sits at the intersection of several map traditions:

* The **roguelike dungeon** tradition: dense local tiles, turn-based tactics, item interaction.
* The **hexcrawl** tradition: long-distance exploration, unknown terrain, resource attrition.
* The **survival sandbox** tradition: hunger, warmth, weather, shelter, crafting, and scavenging.
* The **simulationist worldgen** tradition: persistent worlds, procedural sites, emergent history.
* The **logistics game** tradition: vehicles, supplies, routes, bases, and expanding operational reach.

The most CDDA-like systems make the map do more than display geography. They make it answer strategic questions:

* What can I see?
* What do I know?
* What can I carry?
* How far can I go?
* What happens if I arrive tired, hungry, cold, injured, or noisy?
* What changes while I am away?
* What does this place imply before I enter it?
* What does it become after I leave?

For the target solution, a strong CDDA-like map is therefore not just a world generator or a set of interesting travel rules. It is a **persistent player-scale decision engine** where geography, information, simulation, logistics, and prior player action continuously reshape each other.

Z-axis support strengthens that engine by adding stacked navigation, subsurface exploration, vertical hazards, and richer local persistence. But the core requirement is broader: the map must be durable, revisitable, locally interactive, and strategically readable.

# Continent Environment and Biomes

## Purpose

This document describes the major environmental logic of the game region: its scale, climate, geology, hydrology, biomes, flora, fauna, and ecological rules. It is intended as background guidance for world generation, overland map design, materials, creature placement, settlement placement, encounter design, and dungeon-transition logic.

The document is not a strict simulation specification. It is a design reference. When implementation choices need to be made, the key principle is that the environment should feel like a coherent living region shaped by unstable water, karst drainage, wet forests, volcanic mountains, and highly adaptable wildlife.

## High-Level Identity

The game takes place on a large isolated landmass roughly comparable in area to Greenland or Alaska. Whether it is technically a continent, island, microcontinent, or lost subcontinental fragment is less important than how it behaves as a game space: it is large enough to contain multiple climate gradients, mountain systems, coasts, river basins, regional cultures, endemic species, and long ecological histories.

The landmass is dominated by humid forests, dynamic karst lowlands, spring-fed wetlands, sinking lakes, limestone gorges, volcanic highlands, dead lava tubes, peat moors, storm coasts, and cold upland forests. It is a wet, porous, unstable place. Water appears, disappears, reverses, floods, drains underground, resurfaces through springs, and reshapes travel routes.

The strongest environmental identity is:

> A humid karst-and-volcanic landmass where lakes vanish through ponors, estavelles reverse between spring and sink, forests grow over limestone caverns and dead lava tubes, and wildlife survives by following water across mud, caves, ponds, springs, and seasonal corridors.

## Scale and Regional Structure

The landmass is large enough to support broad regional variation while still having a unified environmental identity.

Approximate scale reference:

- Comparable to Greenland or Alaska in broad area.
- Large enough for multiple major watersheds.
- Large enough for separate coastal, lowland, foothill, mountain, and highland biomes.
- Large enough for endemic flora and fauna.
- Large enough for meaningful regional isolation.
- Large enough for weather systems to differ by coast, elevation, and rain shadow.

The region should not feel like a theme park collection of unrelated biomes. It should feel like one large, geologically complex landmass with repeated ecological rules.

The core environmental gradient is:

1. Storm coast.
2. Coastal temperate rainforest.
3. Estuaries, marshes, and brackish lowlands.
4. Karst wet forest.
5. Sinking lake basins and spring gardens.
6. Limestone gorges and sinkhole forests.
7. Foothill hardwood and mixed forest.
8. Volcanic cloud forest.
9. Dead lava-tube forest.
10. Basalt barrens, highland peat moors, tarns, and subalpine heath.

## Real-World Inspirational Anchors

The landmass draws partial inspiration from several real-world regions, but it is not a direct copy of any one of them.

Primary inspirations:

- The Colchis Triangle: humid, relict, lush, forested, rugged, and biologically old.
- The Valdivian Coast: stormy temperate rainforest, coastal mountains, huge wet forests, and oceanic climate.
- The Tarkine and Tasmanian Central Highlands: ancient wet forest, peatlands, button-grass plains, cold uplands, and rugged wilderness.
- The Carolina Fall Line to the Blue Ridge: transition from lowland/coastal plain through piedmont and foothills into older mountains, with mixed hardwood forests, rivers, ravines, and settlement corridors.

The setting combines these inspirations with a more extreme and more game-functional karst and volcanic geology.

## Climate

The overall climate is humid, ocean-influenced, and strongly shaped by elevation. Rainfall is common across much of the landmass, but surface water is unreliable because of karst drainage. A wet place can still have dry basins, disappearing streams, and exposed mudflats.

### Major Climate Patterns

- Coastal regions are stormy, foggy, and rain-soaked.
- Lowland forests are warm to mild, humid, and biologically dense.
- Karst basins can swing between flooded, muddy, and dry states.
- Foothills are cooler and somewhat more seasonal.
- Mountain forests are cold, misty, and cloud-covered.
- Highland moors are wet, windy, exposed, and often cold.
- Volcanic barrens can be locally dry or thin-soiled even inside a wet macroclimate.

### Seasonal Logic

The landmass should have recognizable hydrological phases rather than a simple summer/winter split.

Important states:

- Wet season: basins fill, springs surge, estavelles act as springs, surface channels connect.
- Draining season: lakes lower, ponors activate, whirlpools and sinking channels appear.
- Mud season: lakebeds become mudflats, fish trails emerge, amphibious wildlife migrates.
- Dry season: springs and underground waters become refuge points, basins crack, cave mouths open.

These states should affect overland traversal, wildlife placement, available resources, dungeon entrances, and settlement behavior.

## Geology

The landmass has two major geological personalities: karst lowlands and volcanic mountains.

### Karst Province

The lowlands and foothills include extensive soluble rock: limestone, dolomite, marble-like bands, and related carbonate formations. These rocks create caves, sinkholes, ponors, disappearing streams, underground rivers, springs, karst windows, natural bridges, and unstable basins.

Common karst features:

- Sinkholes.
- Dolines.
- Ponors.
- Estavelles.
- Karst windows.
- Limestone pavements.
- Natural bridges.
- Cave mouths.
- Underground rivers.
- Spring lines.
- Collapse basins.
- Sinking lakes.
- Flowstone caverns.

The karst province should not be treated as cosmetic terrain. It is the main reason the surface ecology behaves dynamically.

### Volcanic Province

The inland mountains contain extinct or long-dead volcanic systems. These include basalt flows, lava fields, scoria slopes, ash deposits, basalt cliffs, old volcanic ridges, and extensive dead lava tubes.

Common volcanic features:

- Basalt pavement.
- Basalt cliffs.
- Scoria slopes.
- Old lava fields.
- Dead lava tubes.
- Lava-tube skylights.
- Collapsed lava tubes.
- Basalt arches.
- Volcanic ash pockets.
- Thin-soiled barrens.
- Cold-air vents.
- Tube-trench forests.

The volcanic province should feel different from the karst province. Karst caves are pale, wet, dissolved, branching, and water-shaped. Lava tubes are darker, more linear, more volcanic, often drier, and shaped by old flows.

### Geological Transition

One of the most important world-generation transitions is from limestone karst to volcanic mountain terrain.

Karst terrain:

- Pale rock.
- Sinkholes.
- Springs.
- Ponors.
- Flowstone caves.
- Underground rivers.
- Disappearing streams.

Volcanic terrain:

- Dark basalt.
- Lava tubes.
- Skylights.
- Collapsed tube trenches.
- Basalt ridges.
- Scoria.
- Dry or seep-fed underground passages.

The player should be able to recognize this transition visually and mechanically.

## Hydrology

Hydrology is the central environmental system of the landmass.

Water does not simply flow downhill on the surface. It moves through a three-dimensional network of surface streams, temporary channels, sinkholes, ponors, estavelles, underground rivers, spring vents, karst windows, cave lakes, and lava-tube seepage systems.

### Core Hydrological Rules

1. Surface water is often temporary.
2. A lake that appears closed may drain underground.
3. A dry basin may later become a lake.
4. A spring can become a sink under different groundwater conditions.
5. Animal paths often follow moisture corridors rather than human roads.
6. Caves are not separate from the surface; they are part of the same water system.
7. Springs are ecological anchors.
8. Ponors and estavelles are both hazards and transition points.
9. Mud is not empty terrain; it is active habitat.
10. Dryness is relative: even dry basins may contain buried, dormant, or underground life.

### Sinking Lakes

Some lakes appear not to drain, but they do drain through ponors, cracks, fissures, or hidden cave systems. These lakes may shift between several states:

- Full lake.
- Lowering lake.
- Whirlpool or active sink phase.
- Mudflat basin.
- Cracked dry basin.
- Refilled lake.

Sinking lake basins are major landmark biomes. They can reveal cave entrances, old structures, stranded docks, animal trails, skeletons, fish routes, mineral deposits, or buried ruins when drained.

### Ponors

Ponors are surface openings where water drains into the underground system. In gameplay terms, they can serve as:

- Hydrological sinks.
- Hazards.
- Dungeon entrances.
- Seasonal features.
- Water-flow logic nodes.
- Wildlife corridors.
- Sound/visual cues for underground space.

A ponor may be submerged in wet periods and exposed during dry periods.

### Estavelles

Estavelles are reversible features that can act as either springs or sinks depending on groundwater pressure and regional hydrological state.

They are especially useful for dynamic map design because the same location can behave differently across the season cycle.

Possible estavelle states:

- Spring mode: water rises from below.
- Sink mode: water drains downward.
- Transitional mode: bubbling, sucking, whirlpooling, pulsing, or unstable.
- Dry mode: exposed throat, mud basin, cave-breathing hole.

Estavelle marshes should be among the most distinctive lowland environments.

### Springs

Springs are stable or semi-stable water sources. They create ecological refuges during dry phases and settlement anchors for people.

Spring environments may include:

- Clear pools.
- Moss gardens.
- Fern walls.
- Tufa terraces.
- Watercress-like vegetation.
- Fish nurseries.
- Amphibian breeding sites.
- Predator activity.
- Shrines, mills, camps, or settlements.

### Karst Windows

Karst windows are places where an underground stream briefly appears at the surface. They can create deep blue pools, cold microclimates, rare plants, and mysterious fish appearances.

These are excellent small landmarks and transition features.

### Underground Waters

Underground waters include cave rivers, seep pools, flooded chambers, hidden streams, and refuge lakes. These are not just dungeon decoration. They are part of the surface ecology. During dry periods, many animals retreat into underground waters or remain near cave mouths.

## Major Biomes

### Storm Coast

The storm coast is exposed, wet, windy, and rugged. It contains cliffs, pocket beaches, estuaries, coastal rainforest, sea caves, driftwood fields, kelp wrack, salt marshes, and fog banks.

Common materials:

- Rock.
- Sand.
- Gravel.
- Salt marsh.
- Driftwood.
- Shallow water.
- Deep water.
- Coastal forest floor.

Design role:

- Boundary region.
- Starting-port candidate.
- Weather identity.
- Trade and exploration corridor.
- Maritime hazard zone.

### Coastal Temperate Rainforest

This is a lush, ocean-fed forest with dense canopy, moss, ferns, nurse logs, saturated soils, and frequent fog.

Common features:

- Huge trees.
- Fern understory.
- Moss-covered trunks.
- Fallen logs.
- Root tangles.
- Ravines.
- Wet cliffs.
- Streamlets.
- Coastal fog.

Design role:

- Signature forest biome.
- Early-to-mid exploration environment.
- Strong atmosphere.
- Wildlife-rich terrain.
- Resource-rich but visually dense.

### Karst Wet Forest

This is the central lowland/foothill biome. It is wet forest growing over porous limestone terrain.

Common features:

- Sinkholes.
- Limestone outcrops.
- Cave mouths.
- Disappearing streams.
- Springs.
- Mossy stone.
- Fern basins.
- Dolines.
- Natural bridges.
- Wet trails.
- Fish trails.

Design role:

- Primary biome for the landmass.
- Home to dynamic hydrology.
- Strong source of cave entrances.
- Ecological core for amphibious wildlife.

### Sinkhole Forest

Sinkhole forests are enclosed or semi-enclosed basins with unique microclimates. Some are lush, some cold, some stagnant, some dangerous, and some connected to caves.

Variants:

- Fern sinkhole.
- Cold-air sinkhole.
- Blackwater sinkhole.
- Collapse sinkhole.
- Sacred sinkhole.
- Predator sinkhole.
- Spring-fed sinkhole.

Design role:

- Local landmark.
- Micro-biome.
- Encounter pocket.
- Rare resource site.
- Cave access point.

### Sinking Lake Basin

A sinking lake basin is a lake, marsh, mudflat, or dry basin depending on hydrological state.

States:

- Full lake.
- Shrinking lake.
- Draining basin.
- Mudflat.
- Cracked dry basin.
- Refill pulse.

Common features:

- Ponor throat.
- Ringed water lines.
- Stranded docks.
- Mud ramps.
- Fish trails.
- Residual pools.
- Burrow fields.
- Exposed cave mouths.

Design role:

- Major landmark biome.
- Seasonal traversal changes.
- Wildlife congregation.
- Revealed secrets.
- Hydrology demonstration.

### Estavelle Marsh

Estavelle marshes are reversible wetland systems. They may bubble with spring water in one season and drain into the underground in another.

Common features:

- Bubbling vents.
- Sinking pools.
- Reeds.
- Saturated mud.
- Clear spring patches.
- Whirlpools.
- Soft ground.
- Fish and amphibian migrations.

Design role:

- Dynamic wetland.
- Hydrological puzzle terrain.
- Wildlife-rich environment.
- Hazard and resource zone.

### Spring Garden

Spring gardens are reliable water refuges around springs and seeps.

Common features:

- Clear pools.
- Moss.
- Ferns.
- Wet stone.
- Tufa-like terraces.
- Shaded water.
- Fish nurseries.
- Animal tracks.
- Human structures.

Design role:

- Safe-ish oasis.
- Settlement anchor.
- Wildlife hub.
- Rare plant area.
- Dry-season refuge.

### Amphibious Mudflat

Mudflats appear where water has recently drained or where shallow basins fluctuate.

Common features:

- Slick mud.
- Shallow pools.
- Cracked edges.
- Algal mats.
- Burrows.
- Fish trails.
- Mudskipper display grounds.
- Octopus burial sites.
- Mustelid tracks.

Design role:

- Wildlife behavior showcase.
- Traversal challenge.
- Seasonal terrain.
- Predator/prey interaction zone.

### Limestone Gorge

Limestone gorges are steep, wet, cave-riddled valleys where surface and underground water interact.

Common features:

- Pale cliffs.
- Waterfalls.
- Cave mouths.
- Natural bridges.
- Ledges.
- Springs.
- Disappearing streams.
- Fern walls.
- Collapse chambers.

Design role:

- Traversal gate.
- Visual spectacle.
- Cave entrance zone.
- Region boundary.
- Vertical encounter space.

### Foothill Hardwood Forest

This biome is a mixed woodland and settlement corridor between karst lowlands and mountains.

Common features:

- Rolling hills.
- Mixed hardwoods.
- Creeks.
- Old roads.
- Fields.
- Orchards.
- Pastures.
- Mills.
- Secondary forest.
- Ravines.

Design role:

- Human-modified edge.
- Transitional biome.
- Road and settlement placement.
- More open terrain than rainforest.

### Volcanic Cloud Forest

As the land rises into volcanic mountains, wet forest becomes colder, mistier, darker, and more basaltic.

Common features:

- Basalt boulders.
- Cloud cover.
- Moss mats.
- Shorter trees.
- Gnarled trunks.
- Cold streams.
- Root curtains.
- Lava-tube entrances.
- Fog.

Design role:

- Mountain transition.
- Mood shift from karst to volcanic terrain.
- Access to lava-tube systems.
- Late-stage forest biome.

### Dead Lava-Tube Forest

This is forest growing over old lava-tube networks.

Common features:

- Skylights.
- Collapsed tube trenches.
- Tube mouths.
- Cold vents.
- Mossy basalt.
- Root curtains.
- Linear depressions.
- Hollow sounds.
- Dry underground passages.

Design role:

- Signature mountain biome.
- Lava-tube dungeon access.
- Distinct from karst caves.
- Strong traversal identity.

### Basalt Barrens

Basalt barrens are exposed volcanic surfaces with thin soils, sparse vegetation, lichens, moss, gravel, and broken rock.

Common features:

- Basalt pavement.
- Scoria.
- Ash pockets.
- Sparse shrubs.
- Lichens.
- Wind exposure.
- Broken lava.
- Collapsed flows.

Design role:

- Open contrast to dense forest.
- Harsh terrain.
- High-visibility travel.
- Geological marker.
- Resource zone.

### Highland Peat Moor

Highland peat moors are cold, wet, open uplands with peat, tarns, bog pools, button-grass-like vegetation, and stunted shrubs.

Common features:

- Peat.
- Sphagnum.
- Bogs.
- Tarn fields.
- Wet grassland.
- Stunted trees.
- Wind.
- Cold rain.
- Exposed ridges.

Design role:

- Tarkine/Central Highlands influence.
- Open wet terrain.
- Visibility contrast.
- Hazardous ground.
- Ancient preserved remains or ruins.

### Subalpine Heath and Balds

The highest accessible areas contain exposed ridges, grass balds, heath, basalt outcrops, cold pools, and sparse scrub.

Common features:

- Heath.
- Rock.
- Scree.
- Low shrubs.
- Wind.
- Snow patches where appropriate.
- High visibility.
- Cold lakes.

Design role:

- Climactic highland terrain.
- Exposed traversal.
- Large-scale map reveal.
- Spiritual or landmark sites.

## Flora

The flora should reflect a wet, ancient, highly regional landmass with strong microclimates. Flora is not just scenery. It indicates water, soil, elevation, cave proximity, fire history, and hydrological state.

### Major Plant Communities

#### Coastal Rainforest Flora

Typical forms:

- Large evergreen canopy trees.
- Broadleaf evergreen trees.
- Conifer-like giants where appropriate.
- Tree ferns.
- Mossy nurse logs.
- Lichens.
- Epiphytes.
- Fern carpets.
- Salt-tolerant shrubs near coast.

Design use:

- Dense visual occlusion.
- Wet atmosphere.
- Rich organic material.
- Fallen-log traversal.
- Moss and fern material placement.

#### Karst Forest Flora

Karst flora should vary sharply over short distances because soil depth, drainage, and rock exposure change constantly.

Typical forms:

- Fern basins.
- Moss-covered limestone.
- Root mats.
- Shade-tolerant shrubs.
- Spring plants.
- Cave-mouth mosses.
- Trees rooted around cracks and sinkholes.
- Plants growing from limestone ledges.

Design use:

- Visual indicator of hidden water.
- Clue for sinkholes and cave mouths.
- Rare plants in dolines and spring gardens.
- Drier, thinner vegetation on exposed limestone pavement.

#### Wetland and Mudflat Flora

Typical forms:

- Reeds.
- Sedges.
- Rushes.
- Algal mats.
- Floating plants.
- Mudflat annuals.
- Pond-edge herbs.
- Watercress-like spring plants.
- Burrow-stabilizing root mats.

Design use:

- Indicates water depth and seasonal state.
- Supports mudskipper and walking-fish habitats.
- Creates concealment and soft-ground hazards.
- Marks spring reliability.

#### Highland Peat Flora

Typical forms:

- Sphagnum mats.
- Button-grass-like tussocks.
- Heath shrubs.
- Bog herbs.
- Stunted trees.
- Lichens.
- Carnivorous or insect-trapping plants if desired.
- Cold bog pool vegetation.

Design use:

- Hazard indication.
- Open terrain texture.
- Resource and preservation zone.
- Cold/wet biome identity.

#### Volcanic Flora

Volcanic flora should show adaptation to thin soil, basalt cracks, ash deposits, and exposed rock.

Typical forms:

- Lichens on basalt.
- Moss on lava rock.
- Dwarf shrubs.
- Hardy grasses.
- Rooting plants in cracks.
- Cloud-forest trees on deeper soils.
- Ferns near vents and seepage.
- Tube-mouth mosses.

Design use:

- Indicates transition from karst to basalt.
- Marks lava-tube entrances and skylights.
- Creates sharp contrast between barren lava and lush cloud forest.

### Flora as Environmental Signaling

Plants should help players read the terrain.

Examples:

- Thick ferns suggest wet shade, ravines, springs, or sinkholes.
- Mossy limestone suggests karst moisture and possible cave systems.
- Reeds suggest shallow water or seasonal wetlands.
- Algal mats suggest recently exposed mud or shrinking pools.
- Sphagnum suggests peatland and soft ground.
- Lichens on basalt suggest exposed volcanic rock.
- Root curtains suggest cave mouths, skylights, or eroded banks.
- Watercress-like plants suggest reliable spring water.
- Dead reed rings suggest recent high water in a sinking basin.

## Fauna

Fauna on the landmass is shaped by water instability, humid forests, caves, mudflats, and isolation. The most successful animals are adaptable, amphibious, burrowing, semi-aquatic, cave-tolerant, or capable of tracking water across a shifting landscape.

### Ecological Principles

1. Many animals are amphibious or semi-aquatic.
2. Many species use caves, mud, springs, or burrows as refuge.
3. Migration can happen over very short distances between ponds, basins, springs, and underground waters.
4. Predators patrol hydrological bottlenecks.
5. Drying basins create feeding opportunities.
6. Springs become crowded refuge habitats.
7. Mud is a major ecological substrate.
8. Surface and underground food webs are connected.
9. Some animals use seasonal trails not made by humans.
10. Adaptability matters more than specialization in many lowland niches.

### Walking Fish

Walking fish are common and ecologically important. They are not rare monsters. They are part of the everyday wetland food web.

Behaviors:

- Move between ponds during mud season.
- Follow wet trails, seep lines, and shallow rills.
- Gather near springs during dry phases.
- Travel in groups during basin drainage.
- Leave belly, fin, or tail tracks in mud.
- Retreat into ponors, karst windows, or underground channels.
- Become prey for mustelids, birds, reptiles, octopuses, and larger fish.

Design role:

- Environmental indicator.
- Prey species.
- Navigation clue.
- Seasonal movement cue.
- Food resource.
- Signal of nearby water.

### Mudskippers and Amphibious Surface Fish

Mudskippers and related amphibious fish occupy mudflats, pond margins, estavelle marshes, and drying lakebeds.

Behaviors:

- Sunbathe on mud, roots, stones, and logs.
- Display territorially.
- Dive into burrows.
- Feed on insects, larvae, algae, and small aquatic creatures.
- Flee before larger predators.
- Cluster around shrinking pools.

Design role:

- Visible surface wildlife.
- Mudflat animation.
- Alarm behavior.
- Prey base.
- Sign of active wet/dry transition.

### Freshwater Octopuses

Freshwater octopuses are one of the landmass’s most distinctive endemic animals. They occupy spring-fed basins, mudflats, cave pools, slow streams, sinking lake margins, and wet burrow systems.

They are not fully terrestrial animals, but they are capable of short surface excursions across wet mud, moss, rain-soaked stone, and shallow puddle networks.

Behaviors:

- Hide in mud burrows.
- Bury themselves during dry spells.
- Sunbathe briefly on wet mud or warm stones.
- Ambush walking fish near pool edges.
- Retreat into spring pools or cave water.
- Travel during rain, fog, dawn, dusk, or flood pulses.
- Change color and texture against mud, leaf litter, basalt, limestone, or algae.
- Use shells, roots, holes, and stone crevices as dens.

Ecological constraints:

- They require moisture or mud contact.
- They avoid long dry crossings.
- They are most common around stable springs and seasonal basins.
- They survive dry phases by burrowing, retreating underground, or using permanent water refuges.

Design role:

- Signature creature.
- Ambush predator.
- Intelligent environmental actor.
- Mudflat and cave-pool inhabitant.
- Strong indicator of this world’s uniqueness.

### Warm-Weather Otter-Weasels

These are mustelid-like mammals adapted to warm, humid, amphibious lowlands. They behave like flexible marsh otters, weasels, and fishers rather than cold-water marine otters.

Physical tendencies:

- Long body.
- Dense water-shedding coat.
- Semi-webbed feet.
- Strong claws.
- Good burrowing ability.
- Strong smell-tracking.
- Heat tolerance.

Behaviors:

- Patrol pond chains.
- Raid fish trails.
- Dig for buried prey.
- Hunt mudskippers and walking fish.
- Enter cave mouths and spring tunnels.
- Use slides through mud and wet vegetation.
- Den in roots, banks, sinkhole edges, and abandoned burrows.

Design role:

- Common mid-sized predator.
- Dynamic wetland hunter.
- Track-maker.
- Den-based encounter animal.
- Bridge between terrestrial and aquatic food webs.

### Cave Fauna

Cave systems host both true cave specialists and surface animals using caves as refuge.

True cave fauna may include:

- Pale fish.
- Blind crustaceans.
- Cave insects.
- Salamander-like amphibians.
- Cave eels.
- Pale mollusks.
- Root-feeding invertebrates.

Surface-linked cave users may include:

- Walking fish.
- Freshwater octopuses.
- Mustelids.
- Amphibians.
- Bats or bat analogues.
- Predators using cave mouths as ambush sites.

Design role:

- Reinforces connection between surface and underground.
- Provides dungeon ecology.
- Makes caves feel alive rather than empty.
- Supports resource and encounter variety.

### Birds

Birdlife should concentrate around wetlands, coasts, mudflats, forests, and highlands.

Possible groups:

- Wading birds following draining basins.
- Kingfisher-like spring hunters.
- Fish-eating raptors.
- Forest birds in rainforest canopy.
- Carrion birds over drying lakebeds.
- Marsh birds in reeds.
- Cliff nesters in limestone gorges.
- Highland ground birds on moors.

Design role:

- Movement in the sky.
- Ecological signaling.
- Soundscape.
- Predator/scavenger cues.
- Indirect markers of water and prey.

### Reptiles and Amphibians

The lowlands can support reptiles and amphibians adapted to wet/dry cycles.

Possible groups:

- Basin frogs.
- Cave salamanders.
- Mud turtles or analogues.
- Water snakes.
- Small crocodilian-like ambush predators if desired.
- Burrowing amphibians.
- Rock lizards in basalt barrens.

Design role:

- Seasonal emergence.
- Wetland danger.
- Cave ecology.
- Mudflat and spring diversity.

### Large Herbivores and Browsers

Large herbivores should exist but should not dominate the core identity as much as the amphibious fauna.

Possible niches:

- Forest browsers in foothill hardwoods.
- Marsh grazers in reedbeds and wet meadows.
- Highland grazers in moors and heath.
- Small deer-like or tapir-like animals in rainforest.
- Stocky animals adapted to mud and dense vegetation.

Design role:

- Tracks and trails.
- Prey for large predators.
- Settlement interaction.
- Vegetation pressure.
- Hunting systems.

### Large Predators

Large predators should be adapted to terrain.

Possible types:

- Forest ambush predators.
- Marsh-edge predators.
- Cliff and gorge predators.
- Large mustelid relatives.
- Big cats or cat-like analogues in forests.
- Bear-like omnivores in foothills and highlands.
- Large aquatic or semi-aquatic predators in lakes and underground waters.

Design role:

- Regional threat.
- Ecological apex.
- Track and territory system.
- Strong encounter identity.

## Food Webs

### Mudflat Food Web

Base:

- Algae.
- Detritus.
- Insects.
- Larvae.
- Small crustaceans.
- Microfauna.

Middle:

- Mudskippers.
- Walking fish.
- Amphibians.
- Small reptiles.
- Burrowing invertebrates.

Predators:

- Freshwater octopuses.
- Otter-weasels.
- Wading birds.
- Snakes.
- Larger fish during flooded phases.

### Spring Garden Food Web

Base:

- Spring plants.
- Mosses.
- Aquatic vegetation.
- Invertebrates.
- Detritus.

Middle:

- Small fish.
- Amphibians.
- Crayfish-like animals.
- Snails.
- Larvae.

Predators:

- Otter-weasels.
- Octopuses.
- Birds.
- Larger fish.
- Cave-edge predators.

### Cave Water Food Web

Base:

- Washed-in organic matter.
- Root mats.
- Bat guano or equivalent.
- Microbial films.
- Spring nutrients.

Middle:

- Blind fish.
- Crustaceans.
- Cave insects.
- Small amphibians.

Predators:

- Cave eels.
- Octopuses near entrances.
- Mustelids near cave mouths.
- Larger underground fish.

### Forest Food Web

Base:

- Trees.
- Fungi.
- Leaf litter.
- Fruits.
- Seeds.
- Ferns.
- Insects.

Middle:

- Browsers.
- Rodents.
- Birds.
- Amphibians.
- Invertebrates.

Predators:

- Mustelids.
- Forest cats or analogues.
- Raptors.
- Snakes.
- Larger omnivores.

## Human Settlement and Environmental Use

People settle where water is reliable, travel is possible, and food can be gathered or cultivated. In this landmass, that means settlements cluster around springs, river terraces, coastlines, stable lake margins, limestone gorges, foothill corridors, and volcanic passes.

### Settlement-Friendly Environments

- Storm coast harbors.
- Spring gardens.
- River terraces.
- Stable estuary margins.
- Foothill hardwood clearings.
- Limestone gorge crossings.
- Karst windows.
- Highland passes.
- Old lava-tube shelter zones if culturally appropriate.

### Difficult Settlement Environments

- Active sinking lake basins.
- Estavelle marshes.
- Deep karst wet forest.
- Sinkhole fields.
- Highland peat moors.
- Basalt barrens.
- Collapsed lava-tube forests.
- Flood-prone mudflats.

### Human Modifications

Common modifications:

- Boardwalks.
- Docks.
- Fish weirs.
- Spring shrines.
- Mills.
- Stone causeways.
- Raised roads.
- Terraced fields.
- Orchards.
- Pastures.
- Drainage channels.
- Cave storage.
- Lava-tube shelters.
- Karst bridges.
- Watch posts at gorge crossings.

Settlements should not erase the environment. They should visibly adapt to it.

## Travel and Traversal

Travel is shaped by water state.

Reliable routes:

- Ridge trails.
- Foothill roads.
- Springline paths.
- Boardwalks.
- River terraces.
- Coast roads.
- Volcanic ridges.

Seasonal routes:

- Dry lakebeds.
- Mud trails.
- Frozen or low-water crossings if applicable.
- Temporary pond chains.
- Drained estavelle basins.
- Exposed cave mouths.

Dangerous routes:

- Sinkhole fields.
- Active ponors.
- Deep mud.
- Collapsed lava tubes.
- Flooding gorges.
- Peat bogs.
- Basalt scree.
- Submerged cave passages.

Animal trails should matter. Some routes are maintained not by people but by repeated wildlife movement: fish trails, mustelid slides, amphibian corridors, and large-browser paths.

## Caves and Underground Spaces

The underground world is not separate from the overland world. It is the hidden half of the same environment.

### Karst Caves

Karst caves are formed by dissolved limestone and active water flow.

Common traits:

- Pale stone.
- Irregular branching.
- Flowstone.
- Stalactites and stalagmites.
- Underground rivers.
- Pools.
- Siphons.
- Collapse chambers.
- Roots near entrances.
- Wet echoes.

Design role:

- Dungeon spaces.
- Hydrology routes.
- Wildlife refuges.
- Seasonal access.
- Hidden travel.

### Lava Tubes

Lava tubes are old volcanic conduits.

Common traits:

- Dark basalt.
- Linear tunnel shapes.
- Skylights.
- Collapsed trenches.
- Dry floors.
- Cold vents.
- Root curtains.
- Rough flow textures.
- Basalt benches.

Design role:

- Mountain dungeons.
- Shelter.
- Traversal networks.
- Volcanic identity.
- Contrast with karst caves.

### Cave Mouth Ecotones

Every cave mouth should feel like a transition zone.

Typical sequence:

1. Surface forest, mudflat, gorge, or basalt slope.
2. Damp entrance vegetation.
3. Moss, roots, animal tracks.
4. Twilight zone with bats, insects, fungi, dripping water, or cold air.
5. Deep cave or lava tube.

This gradient should be reflected in map materials and encounter placement.

## Biome-to-Material Implications

The material system should be able to represent the world’s environmental logic.

Important material families:

- Vegetation: forest floor, fern understory, moss, reedbed, heath.
- Mud and soil: mud, deep mud, mudflat, cracked mud, clay, silt, gravel, scree.
- Water: shallow water, deep water, flowing water, spring water, sinking water, estavelle water, stagnant water, bog water, underground water.
- Karst: limestone, limestone pavement, limestone cliff, cave floor, cave wall, cave mouth, flowstone, ponor, sinkhole edge.
- Volcanic: basalt, basalt pavement, basalt cliff, scoria, volcanic ash, lava-tube floor, lava-tube wall, lava-tube skylight, collapsed lava tube.
- Peatland: peat, peat bog, sphagnum, bog pool, tarn, button grass.
- Built/modified: road, track, trail, animal trail, fish trail, boardwalk, bridge, dock, building floor, wood wall, stone wall, ruin floor, ruin wall, field, orchard, pasture, clearcut.

Materials should not carry all meaning alone. Hydrology role, wetness, substrate, biome, and surface flags should exist separately where possible.

## Biome-to-Hydrology Implications

Hydrology should be represented as an explicit layer, not only as water tiles.

Important hydrology roles:

- None.
- Surface channel.
- Underground channel.
- Spring.
- Seep.
- Ponor.
- Estavelle.
- Temporary pool.
- Permanent pool.
- Sinking lake.
- Karst window.

Important wetness states:

- Dry.
- Damp.
- Wet.
- Saturated.
- Shallow flooded.
- Deep flooded.

This allows the same location to change state without becoming a different world feature.

Example:

A sinking lake basin may contain:

- Deep water in wet season.
- Sinking water during drainage.
- Mudflat in mud season.
- Cracked mud in dry season.
- Ponor exposed during dry season.
- Fish trails during mud season.
- Spring refuges that remain wet year-round.

## World Generation Guidance

The overland generator should produce ecological relationships, not just noise fields.

### Required Relationships

- Springs should appear near karst boundaries, limestone gorges, and basin edges.
- Ponors should appear in sinking basins, low points, and karst plains.
- Estavelles should appear in marshy karst basins.
- Sinking lakes should have hidden or explicit underground connections.
- Fish trails should connect shrinking pools, springs, and mudflats.
- Cave mouths should cluster around limestone cliffs, sinkholes, gorges, and ponors.
- Lava-tube entrances should occur in volcanic mountain zones, basalt forests, collapsed tube trenches, and skylights.
- Peat moors should occur in cold wet highlands, not random lowland tiles.
- Basalt barrens should occur near volcanic ridges, lava fields, and highland exposures.
- Settlements should prefer reliable water, travel corridors, and stable ground.

### Region Generation Targets

A representative generated region should include:

- At least one karst wet forest.
- At least one sinking lake basin.
- At least one spring garden.
- At least one ponor or estavelle.
- At least one limestone gorge.
- At least one cave mouth.
- At least one foothill transition.
- At least one volcanic cloud forest.
- At least one lava-tube feature.
- At least one highland peat or basalt barren.
- At least one wildlife corridor.

## Encounter Design Implications

Encounters should be tied to environmental state.

Examples:

- Draining basin: fish migration, predators gathering, exposed ponor.
- Mud season: mudskippers, octopuses, mustelids, burrow fields.
- Dry basin: buried octopus, cracked mud, cave entrance, scavengers.
- Spring garden: crowded refuge, predators nearby, rare plants.
- Estavelle transition: unstable ground, bubbling water, sudden drainage.
- Cave mouth: tracks, roots, damp air, ambush predators.
- Lava-tube skylight: vertical movement, cold vent, hidden tunnel.
- Peat moor: soft ground, preserved remains, low visibility.
- Basalt barrens: exposure, sparse cover, long sightlines.

## Sound and Atmosphere

The environment should be recognizable through sound as much as visuals.

Common sound cues:

- Rain in canopy.
- Dripping cave water.
- Distant underground river.
- Bubbling spring.
- Sucking ponor.
- Mud pops.
- Fish flopping along trails.
- Mudskipper calls or slaps.
- Mustelid chirps, growls, or splashes.
- Octopus movement in shallow water or mud.
- Wind over basalt.
- Hollow resonance over lava tubes.
- Peatland insects and distant birds.
- Coastal storm surf.

## Visual Identity

The landmass should have strong visual contrasts:

- Pale limestone against dark wet forest.
- Dark basalt against moss and fog.
- Clear spring pools against brown mudflats.
- Green fern sinkholes against exposed rock.
- Black lava-tube mouths under bright moss.
- Deep blue karst windows in dense forest.
- Red-brown mud trails across drained lakebeds.
- Silver fog over highland peat.
- White water in limestone gorges.
- Storm-gray coast with saturated forest behind it.

## Implementation Priorities

The environment should influence systems in this order:

1. Biome layer.
2. Substrate layer.
3. Hydrology role layer.
4. Wetness/seasonal state layer.
5. Material layer.
6. Traversal flags.
7. Surface transition features.
8. Wildlife affordances.
9. Settlement placement.
10. Dungeon and underground generation.

The world should not be reduced to `grass`, `road`, and `water`. Those are useful materials, but they do not describe the landmass. The core generator needs to represent karst, wetness, drainage, springs, mud, caves, basalt, lava tubes, and ecological corridors.

## Core Design Summary

The continent is a large humid landmass of forests, karst basins, sinking lakes, springs, gorges, volcanic mountains, lava tubes, peat moors, and storm coasts. It is unified by unstable water. Lakes vanish. Springs surge. Estavelles reverse. Fish walk between ponds. Mustelid predators hunt the mud corridors. Freshwater octopuses sun themselves, bury in mud, and retreat into spring-fed caves. Forests grow over hollow limestone and dead volcanic tubes.

The world should feel old, wet, porous, and alive.

For generation and gameplay purposes, the key environmental promise is:

> The map is not just terrain. It is a dynamic hydrological and ecological machine.

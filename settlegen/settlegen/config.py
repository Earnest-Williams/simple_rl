from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Optional, Sequence, Union


class TextEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


def _norm_text(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _coerce(value, enum_type):
    if isinstance(value, enum_type):
        return value
    text = _norm_text(value)
    aliases = getattr(enum_type, "_ALIASES", {})
    if text in aliases:
        text = aliases[text]
    for member in enum_type:
        if text in {member.value, member.name.lower()}:
            return member
    valid = ", ".join(m.value for m in enum_type)
    raise ValueError(f"Unknown {enum_type.__name__}: {value!r}. Valid values: {valid}")


def _coerce_tuple(values: Iterable, enum_type) -> tuple:
    return tuple(_coerce(v, enum_type) for v in values)


class SettlementKind(TextEnum):
    HAMLET = "hamlet"
    VILLAGE = "village"
    FARMING_VILLAGE = "farming_village"
    FISHING_VILLAGE = "fishing_village"
    MINING_CAMP = "mining_camp"
    MONASTERY = "monastery"
    FORT = "fort"
    MARKET_TOWN = "market_town"
    TOWN = "town"
    WALLED_TOWN = "walled_town"
    PORT_TOWN = "port_town"
    PORT_CITY = "port_city"
    CITY = "city"
    CAPITAL = "capital"
    ANCIENT_CITY = "ancient_city"
    RUINED_CITY = "ruined_city"
    NOMAD_CAMP = "nomad_camp"


SettlementKind._ALIASES = {
    "fortified_outpost": "fort",
    "outpost": "fort",
    "monastery_town": "monastery",
    "mining_town": "mining_camp",
    "hill_village": "village",
    "canal_town": "port_town",
}


class TerrainFeature(TextEnum):
    PLAIN = "plain"
    FOREST = "forest"
    DENSE_FOREST = "dense_forest"
    HILL = "hill"
    MOUNTAIN_PASS = "mountain_pass"
    RIVER = "river"
    STREAM = "stream"
    LAKESIDE = "lakeside"
    BAY = "bay"
    COAST = "coast"
    ISLAND = "island"
    SWAMP = "swamp"
    MARSH = "marsh"
    DELTA = "delta"
    CLIFF = "cliff"
    DESERT_EDGE = "desert_edge"
    OASIS = "oasis"
    FERTILE_VALLEY = "fertile_valley"
    VOLCANIC = "volcanic"


TerrainFeature._ALIASES = {
    "lake": "lakeside",
    "old_growth": "dense_forest",
    "mountains": "mountain_pass",
    "desert": "desert_edge",
    "fen": "marsh",
    "moor": "marsh",
    "hot_springs": "oasis",
    "ancient_road": "plain",
    "caves": "mountain_pass",
}


class MagicMode(TextEnum):
    NO_MAGIC = "no_magic"
    LOW_MAGIC = "low_magic"
    HIGH_MAGIC = "high_magic"
    RUNIC_MAGIC = "runic_magic"
    DIVINE_MAGIC = "divine_magic"
    NECROMANTIC = "necromantic"
    WILD_MAGIC = "wild_magic"
    TECHNO_ARCANE = "techno_arcane"
    # User-friendly aliases.
    NONE = "no_magic"
    LOW = "low_magic"
    HIGH = "high_magic"
    RUNIC = "runic_magic"
    DIVINE = "divine_magic"
    WILD = "wild_magic"
    INDUSTRIAL_ARCANE = "techno_arcane"


MagicMode._ALIASES = {
    "none": "no_magic",
    "no": "no_magic",
    "low": "low_magic",
    "high": "high_magic",
    "runic": "runic_magic",
    "divine": "divine_magic",
    "necromantic_magic": "necromantic",
    "industrial_arcane": "techno_arcane",
}


class SettlementState(TextEnum):
    NEW = "new"
    THRIVING = "thriving"
    ORDINARY = "ordinary"
    DECLINING = "declining"
    SCARCELY_POPULATED = "scarcely_populated"
    GHOST_TOWN = "ghost_town"
    RUINED = "ruined"
    ANCIENT = "ancient"
    OCCUPIED = "occupied"
    PLAGUE_STRUCK = "plague_struck"
    WAR_TORN = "war_torn"
    FLOODED = "flooded"
    UNPOPULATED = "ghost_town"
    POPULATED = "ordinary"
    RECENTLY_BURNED = "war_torn"


SettlementState._ALIASES = {
    "normal": "ordinary",
    "populated": "ordinary",
    "scarce": "scarcely_populated",
    "empty": "ghost_town",
    "unpopulated": "ghost_town",
    "burned": "war_torn",
    "recently_burned": "war_torn",
}


class PopulationMode(TextEnum):
    UNPOPULATED = "unpopulated"
    SCARCE = "scarce"
    NORMAL = "normal"
    CROWDED = "crowded"
    FESTIVAL = "festival"
    REFUGEE_SWOLLEN = "refugee_swollen"


PopulationMode._ALIASES = {
    "populated": "normal",
    "scarcely_populated": "scarce",
    "sparse": "scarce",
}


class BuildingMaterial(TextEnum):
    MOSTLY_WOOD = "mostly_wood"
    MOSTLY_STONE = "mostly_stone"
    MOSTLY_ADOBE = "mostly_adobe"
    MOSTLY_THATCH = "mostly_thatch"
    MOSTLY_BRICK = "mostly_brick"
    MIXED = "mixed"
    RUINED_STONE = "ruined_stone"
    CANVAS_AND_HIDE = "canvas_and_hide"
    ICE_AND_BONE = "ice_and_bone"


BuildingMaterial._ALIASES = {
    "stone": "mostly_stone",
    "wood": "mostly_wood",
    "adobe": "mostly_adobe",
    "brick": "mostly_brick",
    "mostly_reed": "mostly_thatch",
    "reed_and_clay": "mostly_thatch",
    "timber_frame": "mixed",
    "wattle_daub": "mixed",
    "ruined_masonry": "ruined_stone",
}


class LayoutStyle(TextEnum):
    ORGANIC = "organic"
    RADIAL = "radial"
    GRID = "grid"
    LINEAR_ROAD = "linear_road"
    RIVER_STRADDLING = "river_straddling"
    COASTAL = "coastal"
    HILLFORT = "hillfort"
    MONASTIC = "monastic"
    FORTRESS = "fortress"
    RUINS_OVERGROWN = "ruins_overgrown"
    SPINE = "linear_road"
    CANAL = "river_straddling"
    TERRACED = "hillfort"
    CHAOTIC = "organic"


LayoutStyle._ALIASES = {
    "spine": "linear_road",
    "canal": "river_straddling",
    "terraced": "hillfort",
    "chaotic": "organic",
}


class DefenseStyle(TextEnum):
    NONE = "none"
    DITCH = "ditch"
    PALISADE = "palisade"
    STONE_WALL = "stone_wall"
    CASTLE_WALL = "castle_wall"
    WATCHTOWERS = "watchtowers"
    EARTHWORKS = "earthworks"
    DYKE = "dyke"
    MAGIC_WARD = "magic_ward"


class Wealth(TextEnum):
    DESTITUTE = "destitute"
    POOR = "poor"
    MODEST = "modest"
    PROSPEROUS = "prosperous"
    RICH = "rich"
    IMPERIAL = "imperial"


Wealth._ALIASES = {
    "0": "destitute",
    "1": "poor",
    "2": "modest",
    "3": "prosperous",
    "4": "rich",
    "5": "imperial",
}


class Facility(TextEnum):
    CITY_HALL = "city_hall"
    COUNCIL_HOUSE = "council_house"
    COURTHOUSE = "court_house"
    TAX_OFFICE = "tax_office"
    ARCHIVE = "archive"
    CUSTOMS_HOUSE = "customs_house"
    KEEP = "keep"
    CASTLE = "castle"
    STONE_WALL = "stone_wall"
    PALISADE = "palisade"
    TOWER = "tower"
    WATCHTOWER = "watchtower"
    GATEHOUSE = "gatehouse"
    BARRACKS = "barracks"
    ARMORY = "armory"
    PRISON = "prison"
    MOAT = "moat"
    DYKE = "dyke"
    EARTHWORK = "earthwork"
    MARKET = "market"
    MARKET_SQUARE = "market_square"
    INN = "inn"
    TAVERN = "tavern"
    GUILDHALL = "guildhall"
    BANK = "bank"
    CARAVANSERAI = "caravanserai"
    WAREHOUSE = "warehouse"
    GRANARY = "granary"
    BAZAAR = "bazaar"
    SHRINE = "shrine"
    TEMPLE = "temple"
    CHURCH = "church"
    CATHEDRAL = "cathedral"
    MONASTERY = "monastery"
    CEMETERY = "cemetery"
    OSSUARY = "ossuary"
    LIBRARY = "library"
    SCHOOL = "school"
    UNIVERSITY = "university"
    MAGE_TOWER = "mage_tower"
    ARCANE_ACADEMY = "arcane_academy"
    ALCHEMIST = "alchemist"
    RUNESTONE_CIRCLE = "runestone_circle"
    WARDING_OBELISK = "warding_obelisk"
    PORTAL = "portal"
    LEYLINE_WELL = "leyline_well"
    NECROPOLIS = "necropolis"
    BLACKSMITH = "blacksmith"
    FORGE = "forge"
    TANNERY = "tannery"
    CARPENTER = "carpenter"
    POTTER = "potter"
    WEAVER = "weaver"
    BAKERY = "bakery"
    BREWERY = "brewery"
    GLASSWORKS = "glassworks"
    QUARRY = "quarry"
    MINE = "mine"
    KILN = "kiln"
    BRIDGE = "bridge"
    DOCKS = "docks"
    WHARF = "wharf"
    FISHERY = "fishery"
    SHIPYARD = "shipyard"
    LIGHTHOUSE = "lighthouse"
    FERRY = "ferry"
    WATERMILL = "watermill"
    WINDMILL = "windmill"
    FARMSTEAD = "farmstead"
    FIELD = "field"
    ORCHARD = "orchard"
    PASTURE = "pasture"
    BARN = "barn"
    STABLE = "stable"
    APIARY = "apiary"
    VINEYARD = "vineyard"
    HOUSE = "house"
    TENEMENT = "tenement"
    MANOR = "manor"
    HOVEL = "hovel"
    EMPTY_LOT = "empty_lot"
    RUIN = "ruin"
    ANCIENT_VAULT = "ancient_vault"
    BATHHOUSE = "bathhouse"
    # Friendly aliases accepted by value/name coercion below.
    COURT_HOUSE = "court_house"
    WIZARD_TOWER = "mage_tower"
    RUNE_CIRCLE = "runestone_circle"
    WELL = "well"
    FOUNTAIN = "well"
    HARBOR = "docks"
    NET_YARD = "fishery"
    FIELDS = "field"
    FARMS = "farmstead"
    ORCHARDS = "orchard"
    MILL = "watermill"
    POTTERY = "potter"
    WEAVERS = "weaver"
    STABLES = "stable"
    CRYPTS = "necropolis"
    BONE_YARD = "necropolis"
    CURSED_WELL = "leyline_well"
    LEYLINE_NODE = "leyline_well"
    FLOATING_SPIRE = "mage_tower"
    SEWER = "ancient_vault"
    CISTERNS = "well"
    CATACOMBS = "necropolis"
    UNDERCITY = "ancient_vault"
    APOTHECARY = "alchemist"
    HERBALIST = "shrine"
    PLAZA = "market_square"
    CISTERN = "cistern"


Facility._ALIASES = {
    "court_house": "court_house",
    "wizard_tower": "mage_tower",
    "rune_circle": "runestone_circle",
    "rune_stone_circle": "runestone_circle",
    "harbor": "docks",
    "harbour": "docks",
    "net_yard": "fishery",
    "fields": "field",
    "farms": "farmstead",
    "orchards": "orchard",
    "pottery": "potter",
    "weavers": "weaver",
    "stables": "stable",
    "crypts": "necropolis",
    "bone_yard": "necropolis",
    "cursed_well": "leyline_well",
    "leyline_node": "leyline_well",
    "floating_spire": "mage_tower",
    "sewer": "ancient_vault",
    "cisterns": "well",
    "catacombs": "necropolis",
    "undercity": "ancient_vault",
    "apothecary": "alchemist",
    "herbalist": "shrine",
    "plaza": "market_square",
}

# Aliases matching the terminology in the user request.
SettlementCondition = SettlementState
MaterialMode = BuildingMaterial
RoadStyle = LayoutStyle


@dataclass(frozen=True)
class SettlementConfig:
    kind: Union[SettlementKind, str] = SettlementKind.TOWN
    width: int = 96
    height: int = 72
    population_target: Optional[int] = None
    population: Optional[int] = None
    population_mode: Union[PopulationMode, str] = PopulationMode.NORMAL
    state: Union[SettlementState, str] = SettlementState.ORDINARY
    condition: Optional[Union[SettlementState, str]] = None
    magic: Union[MagicMode, str] = MagicMode.LOW_MAGIC
    material: Union[BuildingMaterial, str] = BuildingMaterial.MIXED
    layout: Union[LayoutStyle, str] = LayoutStyle.ORGANIC
    road_style: Optional[Union[LayoutStyle, str]] = None
    defense: Union[DefenseStyle, str] = DefenseStyle.NONE
    wealth: Union[Wealth, str] = Wealth.MODEST
    terrain: Sequence[Union[TerrainFeature, str]] = field(default_factory=lambda: (TerrainFeature.PLAIN,))
    terrain_features: Sequence[Union[TerrainFeature, str]] = field(default_factory=tuple)
    facilities: Sequence[Union[Facility, str]] = field(default_factory=tuple)
    required_facilities: Sequence[Union[Facility, str]] = field(default_factory=tuple)
    forbidden_facilities: Sequence[Union[Facility, str]] = field(default_factory=tuple)
    banned_facilities: Sequence[Union[Facility, str]] = field(default_factory=tuple)
    district_count: Optional[int] = None
    building_density: float = 1.0
    farmland_density: float = 0.8
    water_level: float = 0.45
    forest_density: float = 0.35
    ruin_rate: float = 0.0
    ghost_rate: float = 0.0
    road_width: int = 1
    wall_margin: int = 5
    allow_bridges: bool = True
    allow_subterranean: bool = False
    allow_secret_features: bool = True
    name: Optional[str] = None
    tags: Sequence[str] = field(default_factory=tuple)
    walls: Optional[bool] = None
    palisade: Optional[bool] = None
    moat: Optional[bool] = None
    dyke: Optional[bool] = None

    def normalized(self) -> "SettlementConfig":
        kind = _coerce(self.kind, SettlementKind)
        state = _coerce(self.condition if self.condition is not None else self.state, SettlementState)
        magic = _coerce(self.magic, MagicMode)
        material = _coerce(self.material, BuildingMaterial)
        layout = _coerce(self.road_style if self.road_style is not None else self.layout, LayoutStyle)
        defense = _coerce(self.defense, DefenseStyle)
        wealth = _coerce(self.wealth, Wealth)
        population_mode = _coerce(self.population_mode, PopulationMode)
        terrain = _coerce_tuple(tuple(self.terrain) + tuple(self.terrain_features), TerrainFeature)
        facilities = _coerce_tuple(tuple(self.facilities) + tuple(self.required_facilities), Facility)
        forbidden = _coerce_tuple(tuple(self.forbidden_facilities) + tuple(self.banned_facilities), Facility)

        if self.population is not None:
            pop_target = int(self.population)
        elif self.population_target is not None:
            pop_target = int(self.population_target)
        else:
            pop_target = None

        if self.walls is True and defense == DefenseStyle.NONE:
            defense = DefenseStyle.STONE_WALL
        if self.walls is False and defense in (DefenseStyle.STONE_WALL, DefenseStyle.CASTLE_WALL):
            defense = DefenseStyle.NONE
        if self.palisade is True:
            defense = DefenseStyle.PALISADE
        if self.moat is True:
            defense = DefenseStyle.DITCH
        if self.dyke is True:
            defense = DefenseStyle.DYKE

        if self.width < 32 or self.height < 24:
            raise ValueError("width must be >= 32 and height must be >= 24")
        return replace(
            self,
            kind=kind,
            population_target=pop_target,
            population=pop_target,
            population_mode=population_mode,
            state=state,
            condition=state,
            magic=magic,
            material=material,
            layout=layout,
            road_style=layout,
            defense=defense,
            wealth=wealth,
            terrain=tuple(dict.fromkeys(terrain)),
            terrain_features=tuple(),
            facilities=tuple(dict.fromkeys(facilities)),
            required_facilities=tuple(),
            forbidden_facilities=tuple(dict.fromkeys(forbidden)),
            banned_facilities=tuple(),
            road_width=max(1, int(self.road_width)),
            wall_margin=max(3, int(self.wall_margin)),
            tags=tuple(dict.fromkeys(self.tags)),
        )

    @staticmethod
    def from_strings(*, kind: str = "town", terrain: Iterable[str] = ("plain",), facilities: Iterable[str] = (), **kwargs) -> "SettlementConfig":
        return SettlementConfig(kind=kind, terrain=tuple(terrain), facilities=tuple(facilities), **kwargs).normalized()

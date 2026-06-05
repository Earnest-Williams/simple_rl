"""Procedural medieval/fantasy settlement generator.

Public API:
    from settlegen import SettlementConfig, SettlementGenerator
    settlement = SettlementGenerator(seed=42).generate(SettlementConfig(...))
"""

from .config import (
    BuildingMaterial,
    DefenseStyle,
    Facility,
    LayoutStyle,
    MagicMode,
    MaterialMode,
    PopulationMode,
    RoadStyle,
    SettlementCondition,
    SettlementConfig,
    SettlementKind,
    SettlementState,
    SpatialConstraints,
    TerrainFeature,
    Wealth,
)
from .generator import SettlementGenerator
from .model import (
    Building,
    District,
    FailedFacility,
    GenerationReport,
    MagicSite,
    RoadSegment,
    Settlement,
    TerrainCode,
)

__all__ = [
    "Building",
    "BuildingMaterial",
    "DefenseStyle",
    "District",
    "Facility",
    "FailedFacility",
    "GenerationReport",
    "LayoutStyle",
    "MagicMode",
    "MagicSite",
    "MaterialMode",
    "PopulationMode",
    "RoadSegment",
    "RoadStyle",
    "Settlement",
    "SettlementCondition",
    "SettlementConfig",
    "SettlementGenerator",
    "SettlementKind",
    "SettlementState",
    "SpatialConstraints",
    "TerrainCode",
    "TerrainFeature",
    "Wealth",
]

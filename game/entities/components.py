from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    """Spatial position on the map."""

    x: int
    y: int

    def __iter__(self):
        yield self.x
        yield self.y


@dataclass
class Renderable:
    """Rendering information for an entity."""

    glyph: int
    color_fg: tuple[int, int, int]
    name: str
    blocks_movement: bool = True


@dataclass
class CombatStats:
    """Core combat related statistics."""

    hp: int = 0
    max_hp: int = 0
    mana: float = 0.0
    max_mana: float = 0.0
    fullness: float = 0.0
    max_fullness: float = 0.0
    art_ranks: dict[str, int] = field(default_factory=dict)
    substance_ranks: dict[str, int] = field(default_factory=dict)


@dataclass
class Inventory:
    """Container for items carried by an entity."""

    capacity: int
    items: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class SealTags:
    """Tags that can be consumed to unlock seals or similar mechanics."""

    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FontSources:
    """Sources providing fonts or glyph sets for entities."""

    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VentTargets:
    """Targets that vents or releases can be applied to."""

    targets: list[str] = field(default_factory=list)


@dataclass
class ExpeditionMember:
    """Identity and traits of an expedition member."""

    role_primary: str
    role_secondary: str
    sex: str
    age_band: str
    temperament: str
    fear_tag: str
    ambition_tag: str
    joined_reason: str
    practical_limitation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role_primary": self.role_primary,
            "role_secondary": self.role_secondary,
            "sex": self.sex,
            "age_band": self.age_band,
            "temperament": self.temperament,
            "fear_tag": self.fear_tag,
            "ambition_tag": self.ambition_tag,
            "joined_reason": self.joined_reason,
            "practical_limitation": self.practical_limitation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ExpeditionMember:
        return cls(
            role_primary=data["role_primary"],
            role_secondary=data["role_secondary"],
            sex=data["sex"],
            age_band=data["age_band"],
            temperament=data["temperament"],
            fear_tag=data["fear_tag"],
            ambition_tag=data["ambition_tag"],
            joined_reason=data["joined_reason"],
            practical_limitation=data["practical_limitation"],
        )


@dataclass
class SocialBond:
    """A relational bond between this entity and a target entity."""

    target_entity_id: int
    bond_type: str
    strength: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_entity_id": self.target_entity_id,
            "bond_type": self.bond_type,
            "strength": self.strength,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocialBond:
        return cls(
            target_entity_id=data["target_entity_id"],
            bond_type=data["bond_type"],
            strength=data["strength"],
        )


@dataclass
class LaborProfile:
    """Work and skill profile for an expedition member, tracking availability."""

    base_skills: dict[str, float] = field(default_factory=dict)
    field_skills: dict[str, float] = field(default_factory=dict)
    fatigue: float = 0.0
    availability: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_skills": self.base_skills,
            "field_skills": self.field_skills,
            "fatigue": self.fatigue,
            "availability": self.availability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LaborProfile:
        return cls(
            base_skills=data.get("base_skills", {}),
            field_skills=data.get("field_skills", {}),
            fatigue=data.get("fatigue", 0.0),
            availability=data.get("availability", "available"),
        )

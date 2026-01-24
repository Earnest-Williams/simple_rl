"""Species-specific skill aptitudes.

Defines how quickly different species learn each skill.
Based on DCSS species design with adaptations for simple_rl.

Aptitude values:
  +4: Very fast (2x speed)
  +2: Fast (1.19x speed)
  +1: Slightly fast (1.09x speed)
   0: Normal
  -1: Slightly slow (0.92x speed)
  -2: Slow (0.84x speed)
  -4: Very slow (0.5x speed)
"""

from __future__ import annotations

from typing import Final

from skills.models import Skill

# Type alias for aptitude tables
AptitudeTable = dict[Skill, int]


# Human - Balanced, no special bonuses or penalties
HUMAN_APTITUDES: Final[AptitudeTable] = {
    # Offensive
    Skill.FIGHTING: 0,
    Skill.AXES: 0,
    Skill.MACES_AND_FLAILS: 0,
    Skill.POLEARMS: 0,
    Skill.STAVES: 0,
    Skill.LONG_BLADES: 0,
    Skill.SHORT_BLADES: 0,
    Skill.RANGED_WEAPONS: 0,
    Skill.THROWING: 0,
    Skill.UNARMED_COMBAT: 0,
    # Defensive
    Skill.ARMOUR: 0,
    Skill.DODGING: 0,
    Skill.SHIELDS: 0,
    Skill.STEALTH: 0,
    # Magic
    Skill.SPELLCASTING: 0,
    Skill.CONJURATIONS: 0,
    Skill.HEXES: 0,
    Skill.SUMMONINGS: 0,
    Skill.NECROMANCY: 0,
    Skill.FORGECRAFT: 0,
    Skill.TRANSLOCATIONS: 0,
    Skill.ALCHEMY: 0,
    Skill.FIRE_MAGIC: 0,
    Skill.AIR_MAGIC: 0,
    Skill.ICE_MAGIC: 0,
    Skill.EARTH_MAGIC: 0,
    # Miscellaneous
    Skill.EVOCATIONS: 0,
    Skill.INVOCATIONS: 0,
    Skill.SHAPESHIFTING: 0,
}


# Troll - Strong melee fighter, poor magic
TROLL_APTITUDES: Final[AptitudeTable] = {
    # Offensive - Excellent at brute force combat
    Skill.FIGHTING: 3,
    Skill.AXES: 2,
    Skill.MACES_AND_FLAILS: 2,
    Skill.POLEARMS: 1,
    Skill.STAVES: 1,
    Skill.LONG_BLADES: 1,
    Skill.SHORT_BLADES: -1,
    Skill.RANGED_WEAPONS: -4,
    Skill.THROWING: -2,
    Skill.UNARMED_COMBAT: 4,  # Natural claws
    # Defensive - Tough but not agile
    Skill.ARMOUR: 2,
    Skill.DODGING: -2,
    Skill.SHIELDS: 1,
    Skill.STEALTH: -4,
    # Magic - Very poor at magic
    Skill.SPELLCASTING: -4,
    Skill.CONJURATIONS: -4,
    Skill.HEXES: -4,
    Skill.SUMMONINGS: -4,
    Skill.NECROMANCY: -4,
    Skill.FORGECRAFT: -4,
    Skill.TRANSLOCATIONS: -4,
    Skill.ALCHEMY: -4,
    Skill.FIRE_MAGIC: -4,
    Skill.AIR_MAGIC: -4,
    Skill.ICE_MAGIC: -4,
    Skill.EARTH_MAGIC: -2,  # Slightly better at earth
    # Miscellaneous
    Skill.EVOCATIONS: -3,
    Skill.INVOCATIONS: -2,
    Skill.SHAPESHIFTING: -2,
}


# Deep Elf - Magic specialists, fragile
DEEP_ELF_APTITUDES: Final[AptitudeTable] = {
    # Offensive - Poor at heavy weapons
    Skill.FIGHTING: -2,
    Skill.AXES: -3,
    Skill.MACES_AND_FLAILS: -3,
    Skill.POLEARMS: -1,
    Skill.STAVES: 1,
    Skill.LONG_BLADES: 0,
    Skill.SHORT_BLADES: 2,
    Skill.RANGED_WEAPONS: 1,
    Skill.THROWING: 0,
    Skill.UNARMED_COMBAT: -2,
    # Defensive - Agile but can't wear heavy armor
    Skill.ARMOUR: -3,
    Skill.DODGING: 2,
    Skill.SHIELDS: -1,
    Skill.STEALTH: 2,
    # Magic - Excellent at all magic
    Skill.SPELLCASTING: 3,
    Skill.CONJURATIONS: 2,
    Skill.HEXES: 2,
    Skill.SUMMONINGS: 2,
    Skill.NECROMANCY: 1,
    Skill.FORGECRAFT: 2,
    Skill.TRANSLOCATIONS: 2,
    Skill.ALCHEMY: 2,
    Skill.FIRE_MAGIC: 2,
    Skill.AIR_MAGIC: 2,
    Skill.ICE_MAGIC: 2,
    Skill.EARTH_MAGIC: 1,
    # Miscellaneous
    Skill.EVOCATIONS: 2,
    Skill.INVOCATIONS: 1,
    Skill.SHAPESHIFTING: -2,
}


# Minotaur - Melee specialists with natural weapons
MINOTAUR_APTITUDES: Final[AptitudeTable] = {
    # Offensive - Great at melee
    Skill.FIGHTING: 3,
    Skill.AXES: 2,
    Skill.MACES_AND_FLAILS: 2,
    Skill.POLEARMS: 2,
    Skill.STAVES: 1,
    Skill.LONG_BLADES: 1,
    Skill.SHORT_BLADES: 0,
    Skill.RANGED_WEAPONS: -2,
    Skill.THROWING: 0,
    Skill.UNARMED_COMBAT: 2,
    # Defensive - Tough
    Skill.ARMOUR: 2,
    Skill.DODGING: -1,
    Skill.SHIELDS: 2,
    Skill.STEALTH: -2,
    # Magic - Poor
    Skill.SPELLCASTING: -3,
    Skill.CONJURATIONS: -2,
    Skill.HEXES: -2,
    Skill.SUMMONINGS: -2,
    Skill.NECROMANCY: -2,
    Skill.FORGECRAFT: -3,
    Skill.TRANSLOCATIONS: -2,
    Skill.ALCHEMY: -2,
    Skill.FIRE_MAGIC: -2,
    Skill.AIR_MAGIC: -3,
    Skill.ICE_MAGIC: -2,
    Skill.EARTH_MAGIC: -1,
    # Miscellaneous
    Skill.EVOCATIONS: -2,
    Skill.INVOCATIONS: 1,
    Skill.SHAPESHIFTING: -3,
}


# Draconian - Balanced with slight magic affinity
DRACONIAN_APTITUDES: Final[AptitudeTable] = {
    # Offensive - Decent at combat
    Skill.FIGHTING: 1,
    Skill.AXES: 0,
    Skill.MACES_AND_FLAILS: 0,
    Skill.POLEARMS: 0,
    Skill.STAVES: 0,
    Skill.LONG_BLADES: 0,
    Skill.SHORT_BLADES: 0,
    Skill.RANGED_WEAPONS: -1,
    Skill.THROWING: 0,
    Skill.UNARMED_COMBAT: 2,  # Natural claws
    # Defensive
    Skill.ARMOUR: -1,  # Scales provide natural armor
    Skill.DODGING: 0,
    Skill.SHIELDS: 0,
    Skill.STEALTH: -1,
    # Magic - Good at elemental magic
    Skill.SPELLCASTING: 1,
    Skill.CONJURATIONS: 0,
    Skill.HEXES: 0,
    Skill.SUMMONINGS: 0,
    Skill.NECROMANCY: 0,
    Skill.FORGECRAFT: 1,
    Skill.TRANSLOCATIONS: 0,
    Skill.ALCHEMY: 1,
    Skill.FIRE_MAGIC: 2,  # Dragon breath
    Skill.AIR_MAGIC: 1,
    Skill.ICE_MAGIC: 1,
    Skill.EARTH_MAGIC: 1,
    # Miscellaneous
    Skill.EVOCATIONS: 0,
    Skill.INVOCATIONS: 1,
    Skill.SHAPESHIFTING: -2,
}


# Halfling - Sneaky ranged specialists
HALFLING_APTITUDES: Final[AptitudeTable] = {
    # Offensive - Good with small weapons and ranged
    Skill.FIGHTING: -1,
    Skill.AXES: -2,
    Skill.MACES_AND_FLAILS: -2,
    Skill.POLEARMS: -3,
    Skill.STAVES: 1,
    Skill.LONG_BLADES: -2,
    Skill.SHORT_BLADES: 3,
    Skill.RANGED_WEAPONS: 3,
    Skill.THROWING: 2,
    Skill.UNARMED_COMBAT: -1,
    # Defensive - Agile and stealthy
    Skill.ARMOUR: -2,
    Skill.DODGING: 3,
    Skill.SHIELDS: 0,
    Skill.STEALTH: 4,
    # Magic - Decent
    Skill.SPELLCASTING: 0,
    Skill.CONJURATIONS: 0,
    Skill.HEXES: 1,
    Skill.SUMMONINGS: 0,
    Skill.NECROMANCY: -1,
    Skill.FORGECRAFT: 1,
    Skill.TRANSLOCATIONS: 1,
    Skill.ALCHEMY: 1,
    Skill.FIRE_MAGIC: 0,
    Skill.AIR_MAGIC: 0,
    Skill.ICE_MAGIC: 0,
    Skill.EARTH_MAGIC: 0,
    # Miscellaneous
    Skill.EVOCATIONS: 2,
    Skill.INVOCATIONS: 0,
    Skill.SHAPESHIFTING: 0,
}


# Species aptitude lookup table
SPECIES_APTITUDES: Final[dict[str, AptitudeTable]] = {
    "Human": HUMAN_APTITUDES,
    "Troll": TROLL_APTITUDES,
    "Deep Elf": DEEP_ELF_APTITUDES,
    "Minotaur": MINOTAUR_APTITUDES,
    "Draconian": DRACONIAN_APTITUDES,
    "Halfling": HALFLING_APTITUDES,
}


def get_species_aptitudes(species: str) -> AptitudeTable:
    """Get aptitude table for a species.

    Args:
        species: Species name (case-sensitive)

    Returns:
        Aptitude table mapping skills to aptitude modifiers
        Returns human (all 0) if species not found
    """
    return SPECIES_APTITUDES.get(species, HUMAN_APTITUDES).copy()


def get_skill_aptitude(species: str, skill: Skill) -> int:
    """Get aptitude for a specific skill and species.

    Args:
        species: Species name
        skill: Skill to query

    Returns:
        Aptitude modifier (-5 to +11 typically, but species use -4 to +4)
    """
    aptitudes = get_species_aptitudes(species)
    return aptitudes.get(skill, 0)


def format_aptitude_table(species: str) -> str:
    """Format species aptitudes as readable table.

    Args:
        species: Species to display

    Returns:
        Multi-line formatted table
    """
    aptitudes = get_species_aptitudes(species)

    lines: list[str] = []
    lines.append(f"=== {species} Aptitudes ===")
    lines.append("")

    # Group by category
    categories = {
        "Offensive": [
            Skill.FIGHTING,
            Skill.AXES,
            Skill.MACES_AND_FLAILS,
            Skill.POLEARMS,
            Skill.STAVES,
            Skill.LONG_BLADES,
            Skill.SHORT_BLADES,
            Skill.RANGED_WEAPONS,
            Skill.THROWING,
            Skill.UNARMED_COMBAT,
        ],
        "Defensive": [Skill.ARMOUR, Skill.DODGING, Skill.SHIELDS, Skill.STEALTH],
        "Magic": [
            Skill.SPELLCASTING,
            Skill.CONJURATIONS,
            Skill.HEXES,
            Skill.SUMMONINGS,
            Skill.NECROMANCY,
            Skill.FORGECRAFT,
            Skill.TRANSLOCATIONS,
            Skill.ALCHEMY,
            Skill.FIRE_MAGIC,
            Skill.AIR_MAGIC,
            Skill.ICE_MAGIC,
            Skill.EARTH_MAGIC,
        ],
        "Miscellaneous": [Skill.EVOCATIONS, Skill.INVOCATIONS, Skill.SHAPESHIFTING],
    }

    for category_name, skills in categories.items():
        lines.append(f"--- {category_name} ---")
        for skill in skills:
            apt = aptitudes.get(skill, 0)
            apt_str = f"{apt:+2d}" if apt != 0 else "  0"
            skill_name = skill.name.replace("_", " ").title()
            lines.append(f"  {skill_name:<25} {apt_str}")
        lines.append("")

    return "\n".join(lines)


def list_available_species() -> list[str]:
    """Get list of all species with defined aptitudes.

    Returns:
        List of species names
    """
    return list(SPECIES_APTITUDES.keys())

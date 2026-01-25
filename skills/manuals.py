"""Skill manual system for temporary aptitude bonuses.

Skill manuals are consumable items that provide a temporary +4 aptitude bonus
to a specific skill. The bonus lasts until a certain amount of XP is consumed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from skills.models import ManualBonus, Skill

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry


# Manual XP duration by rarity
MANUAL_XP_COMMON = 150  # Common manuals: 150 XP worth
MANUAL_XP_RARE = 300  # Rare manuals: 300 XP worth
MANUAL_XP_LEGENDARY = 500  # Legendary manuals: 500 XP worth


def consume_manual(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    xp_amount: int = MANUAL_XP_COMMON,
) -> None:
    """Consume a skill manual, granting temporary +4 aptitude.

    Args:
        registry: Entity registry
        entity_id: Entity consuming the manual
        skill: Skill to boost
        xp_amount: XP duration for the bonus (default: 150)
    """
    # Get existing manuals
    manuals = get_active_manuals(registry, entity_id)

    # Check if manual already active for this skill
    if skill in manuals:
        # Extend duration by adding XP
        existing_xp = manuals[skill].remaining_xp
        new_xp = existing_xp + xp_amount
        _update_manual_xp(registry, entity_id, skill, new_xp)
    else:
        # Add new manual bonus
        _add_manual(registry, entity_id, skill, xp_amount)

    # Apply aptitude bonus to skills_df
    _apply_manual_aptitude(registry, entity_id, skill, +4)


def _add_manual(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    xp_amount: int,
) -> None:
    """Add a new manual bonus to entity."""
    # Store in entity component
    manuals = get_active_manuals(registry, entity_id)
    manuals[skill] = ManualBonus(skill=skill, remaining_xp=xp_amount, bonus_aptitude=4)

    # Convert to serializable format
    manual_dict = {
        s.value: {"xp": b.remaining_xp, "bonus": b.bonus_aptitude}
        for s, b in manuals.items()
    }

    registry.set_entity_component(entity_id, "active_manuals", manual_dict)


def _update_manual_xp(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    new_xp: int,
) -> None:
    """Update XP remaining for a manual."""
    manuals = get_active_manuals(registry, entity_id)

    if skill in manuals:
        old_bonus = manuals[skill]
        manuals[skill] = ManualBonus(
            skill=skill,
            remaining_xp=new_xp,
            bonus_aptitude=old_bonus.bonus_aptitude,
        )

        # Save back to entity
        manual_dict = {
            s.value: {"xp": b.remaining_xp, "bonus": b.bonus_aptitude}
            for s, b in manuals.items()
        }
        registry.set_entity_component(entity_id, "active_manuals", manual_dict)


def _apply_manual_aptitude(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    bonus: int,
) -> None:
    """Apply aptitude bonus to skills_df."""
    with registry._skills_lock:
        registry.skills_df = registry.skills_df.with_columns(
            [
                pl.when(
                    (pl.col("entity_id") == entity_id)
                    & (pl.col("skill") == skill.value)
                )
                .then(pl.col("aptitude") + bonus)
                .otherwise(pl.col("aptitude"))
                .alias("aptitude")
            ]
        )


def consume_manual_xp(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    xp_gained: int,
) -> bool:
    """Consume XP from active manual.

    Called automatically during XP awards.

    Args:
        registry: Entity registry
        entity_id: Entity that gained XP
        skill: Skill that gained XP
        xp_gained: Amount of XP gained

    Returns:
        True if manual expired, False otherwise
    """
    manuals = get_active_manuals(registry, entity_id)

    if skill not in manuals:
        return False

    manual = manuals[skill]
    remaining = manual.remaining_xp - xp_gained

    if remaining <= 0:
        # Manual expired
        _remove_manual(registry, entity_id, skill)
        return True
    else:
        # Update remaining XP
        _update_manual_xp(registry, entity_id, skill, remaining)
        return False


def _remove_manual(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
) -> None:
    """Remove an expired manual."""
    manuals = get_active_manuals(registry, entity_id)

    if skill in manuals:
        # Remove aptitude bonus
        _apply_manual_aptitude(registry, entity_id, skill, -4)

        # Remove from active manuals
        del manuals[skill]

        # Save back
        manual_dict = {
            s.value: {"xp": b.remaining_xp, "bonus": b.bonus_aptitude}
            for s, b in manuals.items()
        }
        registry.set_entity_component(entity_id, "active_manuals", manual_dict)


def get_active_manuals(
    registry: EntityRegistry,
    entity_id: int,
) -> dict[Skill, ManualBonus]:
    """Get all active manual bonuses for an entity.

    Args:
        registry: Entity registry
        entity_id: Entity to query

    Returns:
        Dict mapping Skill -> ManualBonus
    """
    manual_dict = registry.get_entity_component(entity_id, "active_manuals")

    if not manual_dict or not isinstance(manual_dict, dict):
        return {}

    # Convert from serialized format
    manuals: dict[Skill, ManualBonus] = {}

    for skill_value, data in manual_dict.items():
        skill = Skill(int(skill_value))
        manuals[skill] = ManualBonus(
            skill=skill,
            remaining_xp=data["xp"],
            bonus_aptitude=data.get("bonus", 4),
        )

    return manuals


def has_active_manual(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
) -> bool:
    """Check if entity has an active manual for a skill.

    Args:
        registry: Entity registry
        entity_id: Entity to check
        skill: Skill to check

    Returns:
        True if manual is active
    """
    manuals = get_active_manuals(registry, entity_id)
    return skill in manuals


def get_manual_info(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
) -> str:
    """Get formatted info about an active manual.

    Args:
        registry: Entity registry
        entity_id: Entity to query
        skill: Skill to check

    Returns:
        Formatted string like "Fire Magic: +4 apt (250 XP left)"
    """
    manuals = get_active_manuals(registry, entity_id)

    if skill not in manuals:
        return f"{skill.name}: No active manual"

    manual = manuals[skill]
    skill_name = skill.name.replace("_", " ").title()

    return f"{skill_name}: +{manual.bonus_aptitude} apt ({manual.remaining_xp} XP left)"


def list_active_manuals(
    registry: EntityRegistry,
    entity_id: int,
) -> list[str]:
    """Get list of all active manual info strings.

    Args:
        registry: Entity registry
        entity_id: Entity to query

    Returns:
        List of formatted manual info strings
    """
    manuals = get_active_manuals(registry, entity_id)

    if not manuals:
        return ["No active manuals"]

    return [get_manual_info(registry, entity_id, skill) for skill in manuals]


# Integration with skill system
def integrate_manual_consumption_with_award_xp(
    registry: EntityRegistry,
    entity_id: int,
    xp_shares: dict[Skill, int],
) -> None:
    """Consume manual XP when skills gain XP.

    Call this after distributing XP to skills.

    Args:
        registry: Entity registry
        entity_id: Entity that gained XP
        xp_shares: Dict mapping Skill -> XP gained
    """
    for skill, xp_gained in xp_shares.items():
        if xp_gained > 0:
            expired = consume_manual_xp(registry, entity_id, skill, xp_gained)

            if expired:
                # Notify that manual expired
                from structlog import get_logger

                log = get_logger()
                log.info(
                    "Skill manual expired",
                    entity_id=entity_id,
                    skill=skill.name,
                )

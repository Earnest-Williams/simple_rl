# game/systems/combat_system.py
"""
Handles combat calculations and actions between entities.
"""
from typing import TYPE_CHECKING

import polars as pl
import structlog

# Import roll_dice from its new location
from utils.helpers import roll_dice
from game.entities.components import CombatStats
from game.effects.handlers import apply_status
from game.systems.death_system import handle_entity_death

if TYPE_CHECKING:
    from utils.game_rng import GameRNG  # Assuming this is importable for type hint

    from game.entities.registry import EntityRegistry
    from game.game_state import GameState
    from game.items.registry import ItemRegistry

log = structlog.get_logger(__name__)

DEFAULT_UNARMED_DAMAGE = "1d2"  # Damage if attacker has no weapon


def handle_melee_attack(
    attacker_id: int,
    defender_id: int,
    gs: "GameState",
    damage_type: str = "physical",
):
    """
    Processes a melee attack from attacker_id to defender_id.
    Calculates damage, applies it, handles messages, and checks for death.
    Currently assumes the action is valid and consumes a turn.
    """
    entity_reg: "EntityRegistry" = gs.entity_registry
    item_reg: "ItemRegistry" = gs.item_registry
    rng: "GameRNG" = gs.rng_instance  # Get RNG from GameState
    game_map = gs.game_map

    att = entity_reg.get_entity_components(
        attacker_id, ["name", "strength", "x", "y"]
    )
    defn = entity_reg.get_entity_components(
        defender_id,
        [
            "name",
            "defense",
            "armor",
            "resistances",
            "vulnerabilities",
            "hp",
            "max_hp",
            "x",
            "y",
        ],
    )

    attacker_name = att.get("name") or "Attacker"
    defender_name = defn.get("name") or "Defender"
    log.debug(
        "Handling melee attack",
        attacker=attacker_name,
        defender=defender_name,
        attacker_id=attacker_id,
        defender_id=defender_id,
    )

    # --- Determine Attacker's Damage ---
    damage_dice = DEFAULT_UNARMED_DAMAGE
    weapon_name = "unarmed"

    # Find equipped weapon(s)
    equipped_ids = entity_reg.get_equipped_ids(attacker_id)
    if equipped_ids:
        main_hand_weapon_id: int | None = None
        off_hand_weapon_id: int | None = None
        two_handed = False

        equipped_items = item_reg.get_entity_equipped(attacker_id).filter(
            pl.col("item_id").is_in(equipped_ids)
        )
        if equipped_items.height > 0:
            items_by_slot = {
                row["equipped_slot"]: row
                for row in equipped_items.iter_rows(named=True)
            }
            main_hand_item = items_by_slot.get("main_hand")
            off_hand_item = items_by_slot.get("off_hand")

            if main_hand_item:
                mid = main_hand_item.get("item_id")
                if mid is not None and item_reg.item_has_flag(mid, "WEAPON"):
                    main_hand_weapon_id = mid
                    two_handed = item_reg.item_has_flag(mid, "TWO_HANDED")

            if off_hand_item and not two_handed:
                oid = off_hand_item.get("item_id")
                if oid is not None and item_reg.item_has_flag(oid, "WEAPON"):
                    off_hand_weapon_id = oid

        # Determine main-hand weapon data
        if main_hand_weapon_id is not None:
            weapon_damage_dice_attr = item_reg.get_item_static_attribute(
                main_hand_weapon_id, "damage_dice", default=None
            )
            if weapon_damage_dice_attr:
                damage_dice = weapon_damage_dice_attr
                weapon_name = (
                    item_reg.get_item_component(main_hand_weapon_id, "name") or "weapon"
                )
                log.debug(
                    "Attacker using weapon",
                    weapon=weapon_name,
                    dice=damage_dice,
                    off_hand_weapon=off_hand_weapon_id,
                    two_handed=two_handed,
                )
            else:
                log.warning(
                    "Equipped weapon has no damage_dice attribute",
                    item_id=main_hand_weapon_id,
                )

        off_hand_dice = None
        if off_hand_weapon_id is not None:
            off_hand_dice = item_reg.get_item_static_attribute(
                off_hand_weapon_id, "damage_dice", default=None
            )
    else:
        log.debug("Attacker is unarmed")

    # --- Calculate Damage ---
    raw_damage = roll_dice(damage_dice, rng)
    if "two_handed" in locals() and two_handed:
        raw_damage = int(raw_damage * 1.5)
    elif "off_hand_dice" in locals() and off_hand_dice:
        off_raw = roll_dice(off_hand_dice, rng)
        raw_damage += max(0, off_raw // 2)
        raw_damage = max(0, raw_damage - 1)
    attacker_strength = att.get("strength") or 0
    defender_defense = defn.get("defense") or 0
    defender_armor = defn.get("armor") or 0
    modified_damage = raw_damage + attacker_strength - defender_defense - defender_armor

    resistances = defn.get("resistances") or {}
    vulnerabilities = defn.get("vulnerabilities") or {}
    multiplier = 1.0
    if isinstance(resistances, dict):
        multiplier *= 1 - float(resistances.get(damage_type, 0))
    if isinstance(vulnerabilities, dict):
        multiplier *= 1 + float(vulnerabilities.get(damage_type, 0))
    final_damage = max(0, int(modified_damage * multiplier))

    # --- Apply Damage & Check Death ---
    defender_stats = CombatStats(
        hp=defn.get("hp") or 0,
        max_hp=defn.get("max_hp") or 0,
    )
    if defender_stats.hp <= 0:
        log.error("Defender missing HP component", defender_id=defender_id)
        return  # Cannot apply damage

    new_hp = max(0, defender_stats.hp - final_damage)
    damage_dealt = defender_stats.hp - new_hp

    log.debug(
        "Damage calculated",
        raw=raw_damage,
        final=final_damage,
        dealt=damage_dealt,
        defender_hp_old=defender_stats.hp,
        defender_hp_new=new_hp,
    )

    # Add Combat Messages
    ax = att.get("x") or 0
    ay = att.get("y") or 0
    dx = defn.get("x") or 0
    dy = defn.get("y") or 0
    visible = game_map.visible[ay, ax] or game_map.visible[dy, dx]

    attack_msg = ""
    damage_msg = ""
    hit_color = (200, 200, 200)  # Default color
    damage_color = (255, 255, 0)  # Yellow for damage

    if attacker_id == gs.player_id:
        attack_msg = f"You attack the {defender_name} with your {weapon_name}!"
        if damage_dealt > 0:
            damage_msg = f"You hit for {damage_dealt} damage!"
            damage_color = (0, 255, 0)  # Green for player dealing damage
        else:
            damage_msg = "You miss!"
            damage_color = (150, 150, 150)
    elif defender_id == gs.player_id:
        attack_msg = f"The {attacker_name} attacks you with its {weapon_name}!"
        if damage_dealt > 0:
            damage_msg = f"You are hit for {damage_dealt} damage!"
            damage_color = (255, 0, 0)  # Red for player taking damage
        else:
            damage_msg = f"The {attacker_name} misses!"
            damage_color = (150, 150, 150)
    else:  # Mob vs Mob
        attack_msg = f"The {attacker_name} attacks the {defender_name}!"
        if damage_dealt > 0:
            damage_msg = f"It hits for {damage_dealt} damage."
        else:
            damage_msg = "It misses."

    if visible:
        if attack_msg:
            gs.add_message(attack_msg, hit_color)
        if damage_msg:
            gs.add_message(damage_msg, damage_color)

    # Update Defender HP
    if damage_dealt > 0:
        update_success = entity_reg.set_entity_component(defender_id, "hp", new_hp)
        if not update_success:
            log.error("Failed to set defender HP after attack", defender_id=defender_id)
            # Continue to death check anyway, HP might conceptually be 0

    # Apply on-hit status effects
    if damage_dealt > 0 and new_hp > 0:
        status_sources: list[int] = []
        if "main_hand_weapon_id" in locals() and main_hand_weapon_id is not None:
            status_sources.append(main_hand_weapon_id)
        if "off_hand_weapon_id" in locals() and off_hand_weapon_id is not None:
            status_sources.append(off_hand_weapon_id)
        for wid in status_sources:
            effects = (
                item_reg.get_item_static_attribute(
                    wid, "on_hit_status_effects", default=[]
                )
                or []
            )
            for effect_params in effects:
                context = {
                    "game_state": gs,
                    "source_entity_id": attacker_id,
                    "target_entity_id": defender_id,
                    "rng": rng,
                }
                try:
                    apply_status(context, effect_params)
                except Exception as e:
                    log.error(
                        "Failed to apply on-hit status",
                        error=str(e),
                        effect=effect_params,
                    )

    # Handle Death [Source [source 53]]
    if new_hp <= 0:
        log.info(f"{defender_name} died.", defender_id=defender_id)
        handle_entity_death(defender_id, gs, killer_id=attacker_id)

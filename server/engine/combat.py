"""Ember Protocol — Combat & Action Resolution Engine
Based on PRD v0.9.1, Section 7.14
"""

from __future__ import annotations
import math
import random
from typing import Optional

from server.models import (
    Agent, Creature, Position, ActionResult, DayPhase, WeatherType,
    ActionType, EquipmentSlot,
)
from server.models.items import ITEM_DB, ItemDef


# ─── Combat Formulas ──────────────────────────────────────────────────

def calc_melee_hit(attacker: Agent, target_pos: Position, target_moving: bool) -> tuple[bool, float]:
    """Melee hit determination. Returns (hit, hit_rate)."""
    dist = attacker.position.manhattan_distance(target_pos)
    if dist > 1:
        return False, 0.0
    rate = 0.80 if target_moving else 1.0
    return random.random() <= rate, rate


def calc_ranged_hit(attacker: Agent, target_pos: Position, weapon: ItemDef,
                    target_moving: bool) -> tuple[bool, float, str]:
    """Ranged hit determination. Returns (hit, hit_rate, range_category)."""
    dist = attacker.position.manhattan_distance(target_pos)
    if dist > weapon.attack_range:
        return False, 0.0, "out_of_range"

    # Determine range category
    if dist <= weapon.optimal_range:
        base_rate = 0.95
        range_cat = "optimal"
    elif dist <= weapon.optimal_range + (weapon.attack_range - weapon.optimal_range) // 2:
        base_rate = 0.70
        range_cat = "effective"
    else:
        base_rate = 0.40
        range_cat = "extreme"

    # Movement penalty
    if target_moving:
        base_rate *= 0.7

    return random.random() <= base_rate, base_rate, range_cat


def calc_damage(attacker: Agent, defender_agi: int, weapon: ItemDef,
                dist: int, is_night: bool, defender_armor_def: int = 0,
                defender_resist_type: str = "", defender_resist_val: float = 0.0) -> tuple[int, dict]:
    """Full damage calculation. Returns (final_damage, breakdown)."""
    # ① Base damage
    base = weapon.damage if weapon.id != "unarmed" else 2

    # ② Distance multiplier
    if weapon.weapon_type == "melee" or weapon.id == "unarmed":
        dist_mult = 1.0
    else:
        if dist <= weapon.optimal_range:
            dist_mult = 1.0
        elif dist <= weapon.optimal_range + (weapon.attack_range - weapon.optimal_range) // 2:
            dist_mult = 0.8
        else:
            dist_mult = 0.6

    # ③ Attribute modifier (AGI difference)
    agi_diff = attacker.attributes.agility - defender_agi
    agi_mod = max(0.75, min(1.25, 1.0 + agi_diff * 0.05))

    # ④ Environment modifier
    env_mod = 0.8 if is_night and weapon.weapon_type == "ranged" else 1.0

    # ⑤ Armor reduction
    armor_reduction = defender_armor_def

    # Calculate
    raw = base * dist_mult * agi_mod * env_mod
    final = max(1, int(math.floor(raw - armor_reduction)))

    # Special resistance (e.g., radiation)
    # This is for special damage types, not applied to base physical

    breakdown = {
        "base": base,
        "distance_dmg_modifier": round(dist_mult, 2),
        "agi_modifier": round(agi_mod, 2),
        "environment_modifier": round(env_mod, 2),
        "armor_reduction": armor_reduction,
        "final": final,
    }
    return final, breakdown


def calc_gather_efficiency(agent: Agent, tool: Optional[ItemDef]) -> tuple[float, bool]:
    """Returns (efficiency_multiplier, can_gather).
    Efficiency = base_output × (1 + tool_bonus) × con_modifier
    Unarmed penalty: efficiency × 0.3, cannot gather hardness > 1
    """
    con_mod = 1.0 + (agent.attributes.constitution - 1) * 0.1
    if tool and tool.bonus_value > 0:
        return (1.0 + tool.bonus_value) * con_mod, True
    else:
        return 0.3 * con_mod, True  # Unarmed, slow


def get_unarmed_weapon() -> ItemDef:
    """Return a virtual unarmed weapon definition."""
    return ItemDef(
        id="unarmed", name="Unarmed", name_zh="徒手",
        category=__import__('server.models', fromlist=['ItemCategory']).ItemCategory.WEAPON,
        weapon_type="melee", damage=2, attack_range=1, optimal_range=1,
        energy_cost_attack=2,
    )


def has_line_of_sight(agent_pos: Position, target_pos: Position,
                      building_positions: set[tuple[int, int]]) -> bool:
    """Simple LOS check — Bresenham line, blocked by wall tiles."""
    x0, y0 = agent_pos.x, agent_pos.y
    x1, y1 = target_pos.x, target_pos.y
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        if (x0, y0) != (agent_pos.x, agent_pos.y) and (x0, y0) in building_positions:
            return False
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return True

"""Ember Protocol — Crafting Recipes Database
From PRD v0.9.1, Section 7.4
Ingot ↔ Coin conversion system per PRD 7.4.7
"""

from dataclasses import dataclass, field


@dataclass
class Recipe:
    id: str
    output_id: str
    output_amount: int = 1
    inputs: dict[str, int] = field(default_factory=dict)  # item_id -> amount
    station: str = "hand"  # hand / furnace / workbench
    time_ticks: int = 2
    power_cost: int = 0
    tier: int = 1
    description: str = ""


# ─── Recipe Database ──────────────────────────────────────────────────

RECIPES: list[Recipe] = [
    # ━━━ T1 Hand Recipes (No Facility) ━━━
    Recipe(id="building_block", output_id="building_block", output_amount=1,
           inputs={"stone": 3}, station="hand", time_ticks=2, tier=1,
           description="Basic building material"),

    Recipe(id="repair_kit", output_id="repair_kit", output_amount=1,
           inputs={"carbon": 1, "iron_ingot": 1}, station="hand", time_ticks=3, tier=1,
           description="Restore HP 30"),

    # ━━━ Ingot ↔ Coin Conversion (Hand, No Facility) ━━━
    Recipe(id="copper_ingot_to_coins", output_id="ember_coin", output_amount=5,
           inputs={"copper_ingot": 1}, station="hand", time_ticks=1, tier=1,
           description="Convert 1 Copper Ingot → 5 Ember Coins"),

    Recipe(id="iron_ingot_to_coins", output_id="ember_coin", output_amount=5,
           inputs={"iron_ingot": 1}, station="hand", time_ticks=1, tier=1,
           description="Convert 1 Iron Ingot → 5 Ember Coins"),

    Recipe(id="uranium_ingot_to_coins", output_id="ember_coin", output_amount=20,
           inputs={"uranium_ingot": 1}, station="hand", time_ticks=1, tier=3,
           description="Convert 1 Uranium Ingot → 20 Ember Coins"),

    Recipe(id="gold_ingot_to_coins", output_id="ember_coin", output_amount=50,
           inputs={"gold_ingot": 1}, station="hand", time_ticks=1, tier=3,
           description="Convert 1 Gold Ingot → 50 Ember Coins"),

    Recipe(id="coins_to_copper_ingot", output_id="copper_ingot", output_amount=1,
           inputs={"ember_coin": 5}, station="hand", time_ticks=1, tier=1,
           description="Convert 5 Ember Coins → 1 Copper Ingot"),

    Recipe(id="coins_to_iron_ingot", output_id="iron_ingot", output_amount=1,
           inputs={"ember_coin": 5}, station="hand", time_ticks=1, tier=1,
           description="Convert 5 Ember Coins → 1 Iron Ingot"),

    # ━━━ T1 Smelting Recipes (Furnace Required) ━━━
    Recipe(id="copper_ingot", output_id="copper_ingot", output_amount=1,
           inputs={"raw_copper": 2}, station="furnace", time_ticks=3, power_cost=5, tier=1,
           description="Smelted from raw copper ore"),

    Recipe(id="iron_ingot", output_id="iron_ingot", output_amount=1,
           inputs={"raw_iron": 3}, station="furnace", time_ticks=3, power_cost=5, tier=1,
           description="Smelted from raw iron ore"),

    Recipe(id="uranium_ingot", output_id="uranium_ingot", output_amount=1,
           inputs={"uranium_ore": 4}, station="furnace", time_ticks=6, power_cost=10, tier=3,
           description="Refined uranium ingot"),

    Recipe(id="gold_ingot", output_id="gold_ingot", output_amount=1,
           inputs={"raw_gold": 4}, station="furnace", time_ticks=6, power_cost=10, tier=3,
           description="Refined gold ingot"),

    Recipe(id="carbon", output_id="carbon", output_amount=1,
           inputs={"organic_fuel": 2}, station="furnace", time_ticks=2, power_cost=5, tier=1,
           description="Crafting intermediate"),

    Recipe(id="silicon", output_id="silicon", output_amount=1,
           inputs={"stone": 4}, station="furnace", time_ticks=4, power_cost=5, tier=1,
           description="Refined from stone"),

    # ━━━ T2 Processing Recipes (Workbench Required) ━━━
    Recipe(id="wire", output_id="wire", output_amount=1,
           inputs={"copper_ingot": 1}, station="workbench", time_ticks=2, power_cost=5, tier=2,
           description="Tech component"),

    Recipe(id="carbon_fiber", output_id="carbon_fiber", output_amount=1,
           inputs={"carbon": 2, "iron_ingot": 1}, station="workbench", time_ticks=5, power_cost=5, tier=2,
           description="Advanced material"),

    # ━━━ T2 Tools (Workbench) ━━━
    Recipe(id="basic_excavator", output_id="basic_excavator", output_amount=1,
           inputs={"stone": 3, "organic_fuel": 2}, station="workbench", time_ticks=3, power_cost=5, tier=2,
           description="Mining +50%, durability 50"),

    Recipe(id="standard_excavator", output_id="standard_excavator", output_amount=1,
           inputs={"iron_ingot": 3, "copper_ingot": 1, "carbon": 1}, station="workbench",
           time_ticks=5, power_cost=5, tier=2,
           description="Mining +100%, durability 100"),

    Recipe(id="heavy_excavator", output_id="heavy_excavator", output_amount=1,
           inputs={"iron_ingot": 5, "carbon_fiber": 1, "copper_ingot": 2}, station="workbench",
           time_ticks=8, power_cost=5, tier=2,
           description="Mining +150%, durability 150"),

    Recipe(id="cutter", output_id="cutter", output_amount=1,
           inputs={"iron_ingot": 2}, station="workbench", time_ticks=3, power_cost=5, tier=2,
           description="Chopping +50%, durability 50"),

    # ━━━ T2 Weapons (Workbench) ━━━
    Recipe(id="plasma_cutter_mk1", output_id="plasma_cutter_mk1", output_amount=1,
           inputs={"iron_ingot": 2, "copper_ingot": 1}, station="workbench",
           time_ticks=3, power_cost=5, tier=2, description="Melee 10 damage"),

    Recipe(id="plasma_cutter_mk2", output_id="plasma_cutter_mk2", output_amount=1,
           inputs={"iron_ingot": 4, "carbon_fiber": 1}, station="workbench",
           time_ticks=5, power_cost=5, tier=2, description="Melee 15 damage"),

    Recipe(id="plasma_cutter_mk3", output_id="plasma_cutter_mk3", output_amount=1,
           inputs={"iron_ingot": 6, "carbon_fiber": 2, "gold_ingot": 1}, station="workbench",
           time_ticks=10, power_cost=5, tier=3, description="Melee 22 damage"),

    Recipe(id="pulse_emitter_mk1", output_id="pulse_emitter_mk1", output_amount=1,
           inputs={"iron_ingot": 2, "wire": 2}, station="workbench",
           time_ticks=4, power_cost=5, tier=2, description="Ranged 8 damage, range 6"),

    Recipe(id="pulse_emitter_mk2", output_id="pulse_emitter_mk2", output_amount=1,
           inputs={"iron_ingot": 3, "wire": 3, "carbon_fiber": 1}, station="workbench",
           time_ticks=6, power_cost=5, tier=2, description="Ranged 12 damage, range 8"),

    Recipe(id="pulse_emitter_mk3", output_id="pulse_emitter_mk3", output_amount=1,
           inputs={"iron_ingot": 5, "wire": 4, "carbon_fiber": 2, "uranium_ingot": 1},
           station="workbench", time_ticks=12, power_cost=5, tier=3,
           description="Ranged 18 damage, range 10"),

    # ━━━ T2 Armor & Accessories (Workbench) ━━━
    Recipe(id="radiation_armor", output_id="radiation_armor", output_amount=1,
           inputs={"iron_ingot": 5, "carbon_fiber": 2}, station="workbench",
           time_ticks=10, power_cost=5, tier=2, description="Radiation -50%, physical -2"),

    Recipe(id="searchlight", output_id="searchlight", output_amount=1,
           inputs={"silicon": 2, "iron_ingot": 1, "wire": 1}, station="workbench",
           time_ticks=6, power_cost=5, tier=2, description="Night vision +4"),

    Recipe(id="signal_amplifier", output_id="signal_amplifier", output_amount=1,
           inputs={"iron_ingot": 3, "wire": 3, "silicon": 2}, station="workbench",
           time_ticks=8, power_cost=5, tier=2, description="Comm range 30→80 tiles"),

    Recipe(id="solar_panel", output_id="solar_panel", output_amount=1,
           inputs={"silicon": 2, "carbon_fiber": 1, "wire": 1}, station="workbench",
           time_ticks=8, power_cost=5, tier=2, description="Solar Array component"),

    Recipe(id="battery", output_id="battery", output_amount=1,
           inputs={"iron_ingot": 1, "copper_ingot": 1, "carbon": 1}, station="workbench",
           time_ticks=4, power_cost=5, tier=2, description="Portable energy, restores 30"),

    Recipe(id="radiation_antidote", output_id="radiation_antidote", output_amount=1,
           inputs={"organic_toxin": 2, "carbon": 1}, station="workbench",
           time_ticks=4, power_cost=5, tier=2, description="Removes radiation effect"),
]

RECIPE_MAP: dict[str, Recipe] = {r.id: r for r in RECIPES}


def get_recipes_for_station(station: str) -> list[Recipe]:
    return [r for r in RECIPES if r.station == station]


def find_recipe(recipe_id: str) -> Recipe | None:
    return RECIPE_MAP.get(recipe_id)

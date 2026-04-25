"""Ember Protocol — Comprehensive Test Suite
Tests for all core systems based on PRD v0.9.1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import json
from server.models import (
    Attributes, Position, Agent, ItemInstance, Inventory, Equipment,
    Tile, TerrainType, CoverType, WeatherType, DayPhase, ActiveEffect,
    ActionResult, Building, Creature, CreatureState,
    DAY_CYCLE_TICKS, MAX_INVENTORY_SLOTS, DAY_TICKS, MAX_GROUND_ITEMS_PER_TILE,
)
from server.models.items import ITEM_DB, get_item, get_all_items
from server.models.recipes import RECIPES, RECIPE_MAP, find_recipe
from server.engine.world import WorldMap, DayNightCycle, WeatherSystem, get_zone
from server.engine.combat import calc_melee_hit, calc_ranged_hit, calc_damage, calc_gather_efficiency


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Data Model Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAttributes:
    def test_balanced_build(self):
        attrs = Attributes(constitution=2, agility=2, perception=2)
        assert attrs.max_hp == 110  # 70 + 2*20
        assert attrs.speed == 2     # 1 + floor(2/2)
        assert attrs.base_vision_day == 5  # 3 + 2

    def test_scout_build(self):
        attrs = Attributes(constitution=2, agility=1, perception=3)
        assert attrs.max_hp == 110
        assert attrs.speed == 1     # 1 + floor(1/2)
        assert attrs.base_vision_day == 6  # 3 + 3

    def test_heavy_build(self):
        attrs = Attributes(constitution=3, agility=2, perception=1)
        assert attrs.max_hp == 130  # 70 + 3*20
        assert attrs.speed == 2
        assert attrs.base_vision_day == 4  # 3 + 1

    def test_striker_build(self):
        attrs = Attributes(constitution=1, agility=3, perception=2)
        assert attrs.max_hp == 90   # 70 + 1*20
        assert attrs.speed == 2     # 1 + floor(3/2)
        assert attrs.base_vision_day == 5

    def test_night_vision(self):
        attrs = Attributes(constitution=2, agility=2, perception=2)
        assert attrs.base_vision_night == 3  # max(1, 5-2)


class TestPosition:
    def test_manhattan_distance(self):
        p1 = Position(0, 0)
        p2 = Position(3, 4)
        assert p1.manhattan_distance(p2) == 7

    def test_same_position(self):
        p = Position(5, 5)
        assert p.manhattan_distance(p) == 0


class TestInventory:
    def setup_method(self):
        self.inv = Inventory()

    def test_empty_inventory(self):
        assert self.inv.slots_used == 0
        assert not self.inv.has_item("stone")

    def test_add_stackable(self):
        item = ItemInstance(item_id="stone", amount=10)
        assert self.inv.add_item(item, ITEM_DB)
        assert self.inv.has_item("stone", 10)
        assert self.inv.slots_used == 1

    def test_stack_limit(self):
        # Fill a stack to max (64)
        item = ItemInstance(item_id="stone", amount=64)
        self.inv.add_item(item, ITEM_DB)
        # Adding more should create new slot
        item2 = ItemInstance(item_id="stone", amount=5)
        self.inv.add_item(item2, ITEM_DB)
        assert self.inv.slots_used == 2
        assert self.inv.count_item("stone") == 69

    def test_remove_item(self):
        self.inv.add_item(ItemInstance(item_id="stone", amount=10), ITEM_DB)
        assert self.inv.remove_item("stone", 3)
        assert self.inv.count_item("stone") == 7

    def test_remove_insufficient(self):
        self.inv.add_item(ItemInstance(item_id="stone", amount=2), ITEM_DB)
        assert not self.inv.remove_item("stone", 5)
        assert self.inv.count_item("stone") == 2  # Unchanged

    def test_max_slots(self):
        for i in range(MAX_INVENTORY_SLOTS):
            self.inv.add_item(ItemInstance(item_id=f"item_{i}", amount=1), ITEM_DB)
        # One more should fail for non-stackable items
        # But these items don't exist in ITEM_DB, so add_item returns False
        # Use real items
        inv2 = Inventory()
        for i in range(MAX_INVENTORY_SLOTS):
            inv2.add_item(ItemInstance(item_id="basic_excavator", amount=1), ITEM_DB)
        # Slots filled with non-stackable items
        assert inv2.slots_used == MAX_INVENTORY_SLOTS


class TestEquipment:
    def test_equip_unequip(self):
        attrs = Attributes(2, 2, 2)
        agent = Agent(
            id="test", name="Test", attributes=attrs,
            position=Position(0, 0), spawn_point=Position(0, 0),
            endpoint="http://test", api_key="test",
        )
        agent.inventory.add_item(ItemInstance(item_id="basic_excavator"), ITEM_DB)
        agent.inventory.remove_item("basic_excavator")
        agent.equipment.main_hand = ItemInstance(item_id="basic_excavator")
        assert agent.equipment.main_hand is not None
        assert agent.equipment.main_hand.item_id == "basic_excavator"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Item Database Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestItemDatabase:
    def test_all_resources_exist(self):
        resources = ["stone", "organic_fuel", "raw_copper", "raw_iron", "uranium_ore", "raw_gold", "wood",
                     "acid_blood", "bio_fuel", "organic_toxin", "bio_bone"]
        for r in resources:
            item = get_item(r)
            assert item is not None, f"Missing resource: {r}"
            assert item.category.value == "resource"

    def test_all_materials_exist(self):
        materials = ["copper_ingot", "iron_ingot", "uranium_ingot", "gold_ingot", "ember_coin",
                     "carbon", "silicon", "building_block", "wire", "carbon_fiber"]
        for m in materials:
            item = get_item(m)
            assert item is not None, f"Missing material: {m}"
            assert item.category.value == "material"

    def test_all_tools_exist(self):
        tools = ["basic_excavator", "standard_excavator", "heavy_excavator", "cutter"]
        for t in tools:
            item = get_item(t)
            assert item is not None, f"Missing tool: {t}"
            assert item.category.value == "tool"

    def test_all_weapons_exist(self):
        weapons = ["plasma_cutter_mk1", "plasma_cutter_mk2", "plasma_cutter_mk3",
                   "pulse_emitter_mk1", "pulse_emitter_mk2", "pulse_emitter_mk3"]
        for w in weapons:
            item = get_item(w)
            assert item is not None, f"Missing weapon: {w}"
            assert item.category.value == "weapon"

    def test_weapon_stats(self):
        # Melee weapons
        mk1 = get_item("plasma_cutter_mk1")
        assert mk1.damage == 10
        assert mk1.weapon_type == "melee"
        assert mk1.energy_cost_attack == 2

        mk3 = get_item("plasma_cutter_mk3")
        assert mk3.damage == 22

        # Ranged weapons
        pe1 = get_item("pulse_emitter_mk1")
        assert pe1.damage == 8
        assert pe1.attack_range == 6
        assert pe1.weapon_type == "ranged"
        assert pe1.energy_cost_attack == 3

        pe3 = get_item("pulse_emitter_mk3")
        assert pe3.damage == 18
        assert pe3.attack_range == 10

    def test_tool_tiers(self):
        basic = get_item("basic_excavator")
        assert basic.bonus_value == 0.5
        assert basic.max_hardness == 5

        standard = get_item("standard_excavator")
        assert standard.bonus_value == 1.0
        assert standard.max_hardness == 8

        heavy = get_item("heavy_excavator")
        assert heavy.bonus_value == 1.5
        assert heavy.max_hardness == 10

    def test_armor(self):
        armor = get_item("radiation_armor")
        assert armor.defense == 2
        assert armor.resistance_type == "radiation"
        assert armor.resistance_value == 0.5

    def test_consumables(self):
        repair = get_item("repair_kit")
        assert repair.consumable_effect == "heal"
        assert repair.consumable_value == 30
        assert repair.stack_max == 16

        battery = get_item("battery")
        assert battery.consumable_effect == "restore_energy"
        assert battery.consumable_value == 30

        antidote = get_item("radiation_antidote")
        assert antidote.consumable_effect == "cure_radiation"

    def test_total_item_count(self):
        items = get_all_items()
        assert len(items) >= 30  # Should have 30+ items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Recipe Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRecipes:
    def test_recipe_count(self):
        assert len(RECIPES) >= 20

    def test_hand_recipes(self):
        hand = [r for r in RECIPES if r.station == "hand"]
        assert len(hand) >= 2
        building_block = find_recipe("building_block")
        assert building_block is not None
        assert building_block.inputs == {"stone": 3}

    def test_furnace_recipes(self):
        furnace = [r for r in RECIPES if r.station == "furnace"]
        assert len(furnace) >= 4

    def test_workbench_recipes(self):
        workbench = [r for r in RECIPES if r.station == "workbench"]
        assert len(workbench) >= 15

    def test_basic_excavator_recipe_no_circular_dependency(self):
        """v0.9.1 fix: Basic Excavator uses Stone + Organic Fuel, not Iron/Copper ingots."""
        recipe = find_recipe("basic_excavator")
        assert recipe is not None
        assert "stone" in recipe.inputs
        assert "organic_fuel" in recipe.inputs
        assert "iron_ingot" not in recipe.inputs  # No circular dependency

    def test_all_recipe_outputs_exist_in_items(self):
        for r in RECIPES:
            item = get_item(r.output_id)
            assert item is not None, f"Recipe {r.id} outputs unknown item: {r.output_id}"

    def test_all_recipe_inputs_exist_in_items(self):
        for r in RECIPES:
            for input_id in r.inputs:
                item = get_item(input_id)
                assert item is not None, f"Recipe {r.id} requires unknown item: {input_id}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# World Engine Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWorldMap:
    def setup_method(self):
        self.world = WorldMap(width=50, height=50, seed=42)
        self.world.generate()

    def test_map_size(self):
        assert len(self.world.tiles) == 50 * 50

    def test_all_tiles_have_terrain(self):
        for (x, y), tile in self.world.tiles.items():
            assert tile.l1 in list(TerrainType)

    def test_no_water_in_center(self):
        """Center zone should not have water."""
        center_y = 25
        for x in range(20, 30):
            tile = self.world.get_tile(x, center_y)
            assert tile.l1 != TerrainType.WATER, f"Water at center ({x},{center_y})"

    def test_covers_on_valid_terrain(self):
        for (x, y), tile in self.world.tiles.items():
            if tile.l2 and tile.l2 in COVER_L1_COMPAT:
                compat = COVER_L1_COMPAT[tile.l2]
                assert tile.l1 in compat, f"Invalid cover {tile.l2} on {tile.l1} at ({x},{y})"

    def test_bounds_check(self):
        assert self.world.in_bounds(0, 0)
        assert self.world.in_bounds(49, 49)
        assert not self.world.in_bounds(-1, 0)
        assert not self.world.in_bounds(50, 0)

    def test_zone_distribution(self):
        zones = {}
        for y in range(50):
            zone = get_zone(y, 50)
            zones[zone] = zones.get(zone, 0) + 1
        assert "center" in zones
        assert "T1" in zones
        assert zones["center"] > 0

    def test_deterministic_generation(self):
        """Same seed = same map."""
        world2 = WorldMap(width=50, height=50, seed=42)
        world2.generate()
        for (x, y) in [(10, 10), (25, 25), (40, 40)]:
            t1 = self.world.get_tile(x, y)
            t2 = world2.get_tile(x, y)
            assert t1.l1 == t2.l1, f"Different terrain at ({x},{y})"


class TestDayNightCycle:
    def test_full_cycle(self):
        dnc = DayNightCycle()
        phases = []
        for _ in range(DAY_CYCLE_TICKS):
            phase = dnc.advance()
            phases.append(phase)
        assert DayPhase.DAY in phases
        assert DayPhase.NIGHT in phases
        assert DayPhase.DUSK in phases
        assert DayPhase.DAWN in phases

    def test_day_duration(self):
        dnc = DayNightCycle()
        day_count = 0
        for _ in range(DAY_TICKS):
            dnc.advance()
        # After advancing DAY_TICKS times, we should be at tick DAY_TICKS
        # which is the start of dusk
        assert dnc.current_phase == DayPhase.DUSK

    def test_cycle_wraps(self):
        dnc = DayNightCycle()
        for _ in range(DAY_CYCLE_TICKS + 10):
            dnc.advance()
        assert dnc.tick_in_cycle < DAY_CYCLE_TICKS


class TestWeatherSystem:
    def test_initial_quiet(self):
        ws = WeatherSystem()
        assert ws.current == WeatherType.QUIET

    def test_storm_eventually_occurs(self):
        ws = WeatherSystem()
        storm_occurred = False
        for _ in range(1000):
            weather, events = ws.advance()
            if weather == WeatherType.RADIATION_STORM:
                storm_occurred = True
                break
        assert storm_occurred

    def test_storm_dissipates(self):
        ws = WeatherSystem()
        # Force a storm
        ws.current = WeatherType.RADIATION_STORM
        ws.storm_ticks_remaining = 3
        for _ in range(5):
            weather, events = ws.advance()
        assert ws.current == WeatherType.QUIET


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Combat Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

from server.engine.world import COVER_L1_COMPAT


class TestCombat:
    def setup_method(self):
        self.attacker = Agent(
            id="attacker", name="Attacker",
            attributes=Attributes(2, 2, 2),
            position=Position(5, 5), spawn_point=Position(5, 5),
            endpoint="http://test", api_key="test",
        )
        self.target = Agent(
            id="target", name="Target",
            attributes=Attributes(2, 2, 2),
            position=Position(6, 5), spawn_point=Position(6, 5),
            endpoint="http://test", api_key="test",
        )

    def test_melee_range(self):
        # Adjacent = 1 tile
        hit, rate = calc_melee_hit(self.attacker, self.target.position, False)
        assert rate == 1.0  # Stationary target

    def test_melee_range_too_far(self):
        far_target = Position(20, 20)
        hit, rate = calc_melee_hit(self.attacker, far_target, False)
        assert rate == 0.0

    def test_damage_formula_basic(self):
        weapon = get_item("plasma_cutter_mk1")
        damage, breakdown = calc_damage(
            self.attacker, 2, weapon, 1, False, 0
        )
        assert damage >= 1
        assert breakdown["base"] == 10
        assert breakdown["distance_dmg_modifier"] == 1.0  # Melee

    def test_damage_with_armor(self):
        weapon = get_item("plasma_cutter_mk1")
        damage_no_armor, _ = calc_damage(self.attacker, 2, weapon, 1, False, 0)
        damage_with_armor, bd = calc_damage(self.attacker, 2, weapon, 1, False, 2)
        assert damage_with_armor == max(1, damage_no_armor - 2)

    def test_ranged_distance_falloff(self):
        weapon = get_item("pulse_emitter_mk2")
        # Optimal range (1-3 tiles)
        d1, bd1 = calc_damage(self.attacker, 2, weapon, 2, False, 0)
        assert bd1["distance_dmg_modifier"] == 1.0

        # Effective range (4-6 tiles)
        d2, bd2 = calc_damage(self.attacker, 2, weapon, 5, False, 0)
        assert bd2["distance_dmg_modifier"] == 0.8

        # Extreme range (7-8 tiles)
        d3, bd3 = calc_damage(self.attacker, 2, weapon, 8, False, 0)
        assert bd3["distance_dmg_modifier"] == 0.6

    def test_night_ranged_penalty(self):
        weapon = get_item("pulse_emitter_mk2")
        _, bd_day = calc_damage(self.attacker, 2, weapon, 2, False, 0)
        _, bd_night = calc_damage(self.attacker, 2, weapon, 2, True, 0)
        assert bd_day["environment_modifier"] == 1.0
        assert bd_night["environment_modifier"] == 0.8

    def test_unarmed_damage(self):
        from server.engine.combat import get_unarmed_weapon
        unarmed = get_unarmed_weapon()
        assert unarmed.damage == 2

    def test_gather_efficiency_with_tool(self):
        tool = get_item("basic_excavator")
        eff, can = calc_gather_efficiency(self.attacker, tool)
        assert eff > 1.0  # Should be boosted
        assert can

    def test_gather_efficiency_unarmed(self):
        eff, can = calc_gather_efficiency(self.attacker, None)
        assert eff < 1.0  # Should be penalized


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Integration Tests (Game Engine)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGameEngine:
    def setup_method(self):
        from server.engine.game import GameEngine
        self.engine = GameEngine(map_width=50, map_height=50, seed=42)

    def test_register_agent(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        assert agent.id is not None
        assert agent.tutorial_phase == 0
        assert agent.is_alive()
        assert agent.hp == 110

    def test_agent_starting_inventory(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        # Should have workbench + furnace items
        # (Note: these are placeholder items, real items need to be in ITEM_DB)

    def test_tick_advances(self):
        import asyncio
        asyncio.get_event_loop().run_until_complete(self.engine.tick())
        assert self.engine.current_tick == 1

    def test_build_agent_state(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        state = self.engine.build_agent_state(agent)
        assert "self" in state
        assert "vicinity" in state
        assert "meta" in state
        assert state["self"]["id"] == agent.id

    def test_move_action(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        old_pos = (agent.position.x, agent.position.y)

        # Find a passable adjacent tile
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = old_pos[0] + dx, old_pos[1] + dy
            if self.engine.world.in_bounds(nx, ny):
                tile = self.engine.world.get_tile(nx, ny)
                if tile and tile.l1 != TerrainType.WATER:
                    result = self.engine.resolve_action(agent, {
                        "type": "move", "target": {"x": nx, "y": ny}
                    }, 0)
                    assert result.success
                    assert agent.position.x == nx
                    assert agent.position.y == ny
                    break

    def test_equip_action(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        agent.inventory.add_item(ItemInstance(item_id="basic_excavator"), ITEM_DB)

        result = self.engine.resolve_action(agent, {
            "type": "equip", "item": "basic_excavator", "slot": "main_hand"
        }, 0)
        assert result.success
        assert agent.equipment.main_hand is not None
        assert agent.equipment.main_hand.item_id == "basic_excavator"

    def test_inspect_inventory(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        result = self.engine.resolve_action(agent, {"type": "inspect", "target": "inventory"}, 0)
        assert result.success

    def test_rest_action(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        agent.energy = 50
        result = self.engine.resolve_action(agent, {"type": "rest"}, 0)
        assert result.success
        assert agent.energy > 50

    def test_use_consumable(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        agent.hp = 50
        agent.inventory.add_item(ItemInstance(item_id="repair_kit"), ITEM_DB)

        result = self.engine.resolve_action(agent, {"type": "use", "item": "repair_kit"}, 0)
        assert result.success
        assert agent.hp == 80  # 50 + 30

    def test_use_battery(self):
        attrs = Attributes(2, 2, 2)
        agent = self.engine.register_agent("TestBot", attrs, "http://localhost", "key123")
        agent.energy = 30
        agent.inventory.add_item(ItemInstance(item_id="battery"), ITEM_DB)

        result = self.engine.resolve_action(agent, {"type": "use", "item": "battery"}, 0)
        assert result.success
        assert agent.energy == 60  # 30 + 30


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Run Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

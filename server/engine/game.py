"""Ember Protocol — Game Engine (Tick Loop + Action Resolution)
The core rules engine. No LLM calls — pure state machine.
Based on PRD v0.9.1, Sections 3, 7
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Optional
import uuid
import httpx

from server.models import (
    Agent, Creature, Building, Tile, Position, ActionResult, TickResult,
    GameEvent, ActiveEffect, ItemInstance, Inventory, Equipment,
    Attributes, RadioChannel, CreatureState, ActionType,
    TerrainType, CoverType, WeatherType, DayPhase, AgentDisposition,
    TICK_INTERVAL_SECONDS, MAX_GROUND_ITEMS_PER_TILE, STACK_MAX_RESOURCE,
    POWER_NODE_CAPACITY, POWER_NODE_SUPPLY_RANGE, SOLAR_CHARGE_PER_TICK,
    CRAFT_POWER_COST, AGENT_WIRELESS_CHARGE, BUILTIN_SOLAR_CHARGE, REST_CHARGE,
    HEARTBEAT_TIMEOUT_TICKS, AUTO_LOGOUT_TIMEOUT_TICKS, DROP_POD_SHIELD_RANGE,
    ENCLOSURE_MAX_TILES,
)
from server.models.items import ITEM_DB, get_item
from server.models.recipes import RECIPES, RECIPE_MAP, find_recipe
from server.engine.world import WorldMap, DayNightCycle, WeatherSystem, get_zone, ZONE_RADIATION_PROB
from server.engine.combat import (
    calc_melee_hit, calc_ranged_hit, calc_damage, calc_gather_efficiency,
    get_unarmed_weapon, has_line_of_sight,
)

logger = logging.getLogger("ember.engine")


class GameEngine:
    """The core game engine — pure rules, no LLM."""

    def __init__(self, map_width: int = 100, map_height: int = 100, seed: int = 42):
        self.world = WorldMap(map_width, map_height, seed)
        self.day_night = DayNightCycle()
        self.weather = WeatherSystem()

        # Entity stores
        self.agents: dict[str, Agent] = {}
        self.creatures: dict[str, Creature] = {}
        self.buildings: dict[str, Building] = {}
        self.channels: dict[str, RadioChannel] = {}

        # State
        self.current_tick = 0
        self.running = False
        self._agent_responses: dict[str, list[ActionResult]] = {}

        # Generate world
        self.world.generate()
        self.world.set_buildings_ref(self.buildings)
        logger.info(f"World generated: {map_width}x{map_height}, seed={seed}")

    # ─── Agent Management ─────────────────────────────────────────

    def register_agent(self, name: str, attrs: Attributes,
                       endpoint: str, api_key: str, model_info: str = "") -> Agent:
        """Register a new agent, place drop pod."""
        agent_id = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:4]}"

        # Find spawn position in center zone
        spawn = self._find_spawn_position()
        pod_pos = Position(spawn.x, spawn.y)

        agent = Agent(
            id=agent_id, name=name, attributes=attrs,
            position=Position(spawn.x, spawn.y),
            spawn_point=pod_pos,
            endpoint=endpoint, api_key=api_key, model_info=model_info,
            tutorial_phase=0,
            drop_pod_position=pod_pos,
        )

        # Place starting buildings (workbench + furnace) near spawn
        self._place_starting_buildings(agent)

        self.agents[agent_id] = agent
        logger.info(f"Agent registered: {agent_id} at ({spawn.x},{spawn.y})")
        return agent

    def _place_starting_buildings(self, agent: Agent):
        """Place workbench and furnace buildings near agent spawn point.
        These are the drop pod's built-in facilities."""
        sx, sy = agent.position.x, agent.position.y

        # Try positions near spawn (prefer adjacent, then 2-away)
        for building_type, offset in [("workbench", (1, 0)), ("furnace", (-1, 0))]:
            bx, by = sx + offset[0], sy + offset[1]
            # Find a valid tile (not water, no existing building)
            if not self.world.in_bounds(bx, by):
                bx, by = sx, sy  # Fallback to same tile
            tile = self.world.get_tile(bx, by)
            if not tile or tile.l1 == TerrainType.WATER or tile.l3:
                # Try other adjacent positions
                for dx, dy in [(0, 1), (0, -1), (1, 1), (-1, -1), (2, 0), (-2, 0)]:
                    nx, ny = sx + dx, sy + dy
                    if self.world.in_bounds(nx, ny):
                        t = self.world.get_tile(nx, ny)
                        if t and t.l1 != TerrainType.WATER and not t.l3:
                            bx, by = nx, ny
                            tile = t
                            break

            if not tile:
                continue

            bldg_id = f"{building_type}_{bx}_{by}"
            building = Building(
                id=bldg_id, building_type=building_type,
                position=Position(bx, by), owner_id=agent.id,
                hp=80 if building_type == "workbench" else 100,
                max_hp=80 if building_type == "workbench" else 100,
            )
            self.buildings[bldg_id] = building
            tile.l3 = bldg_id
            logger.info(f"Starting building placed: {building_type} at ({bx},{by}) for {agent.id}")

    def _find_spawn_position(self) -> Position:
        """Find a valid spawn in center zone (Y=center±10% for map)."""
        center_y = self.world.height // 2
        center_x = self.world.width // 2
        for _ in range(100):
            x = center_x + (hash(str(_)) % 40 - 20)
            y = center_y + (hash(str(_ + 100)) % 20 - 10)
            tile = self.world.get_tile(x, y)
            if tile and tile.l1 not in (TerrainType.WATER,):
                return Position(x, y)
        return Position(center_x, center_y)

    def logout_agent(self, agent_id: str):
        """Agent logs out."""
        agent = self.agents.get(agent_id)
        if agent:
            agent.status = "offline"
            logger.info(f"Agent logged out: {agent_id}")

    # ─── Tick Loop ────────────────────────────────────────────────

    async def tick(self) -> TickResult:
        """Execute one game tick."""
        self.current_tick += 1
        result = TickResult(tick=self.current_tick)

        # 1. Advance day/night
        phase = self.day_night.advance()

        # 2. Advance weather
        weather, weather_events = self.weather.advance()
        for ev in weather_events:
            result.world_events.append(GameEvent(
                tick=self.current_tick, event_type="weather",
                data={"type": weather.value, "message": ev}
            ))

        # 3. Process zone radiation
        self._process_zone_radiation(weather)

        # 4. Process agent effects (radiation damage, etc.)
        self._process_agent_effects(weather)

        # 5. Process creature AI
        self._process_creatures()

        # 6. Check heartbeats / auto-logout
        self._check_heartbeats()

        # 7. Process solar charging (power nodes + built-in)
        self._process_solar_charging()

        return result

    async def resolve_tick(self, tick_result: TickResult) -> dict[str, dict]:
        """Collect agent responses and resolve actions. Returns state deltas per agent."""
        deltas = {}

        # Push state to all online agents, collect responses
        tasks = []
        for agent_id, agent in self.agents.items():
            if agent.status != "offline" and agent.is_alive():
                tasks.append(self.push_state_to_agent(agent))

        if not tasks:
            return deltas

        # Use asyncio.gather for parallel push
        import asyncio
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent_id, result in zip(
            [aid for aid, a in self.agents.items() if a.status != "offline" and a.is_alive()],
            results
        ):
            if isinstance(result, Exception):
                logger.warning(f"Agent {agent_id} failed: {result}")
                continue
            if result and isinstance(result, dict):
                actions = result.get("actions", [])
                tick_result.agent_results[agent_id] = []
                agent = self.agents.get(agent_id)
                if agent:
                    for i, action in enumerate(actions):
                        ar = self.resolve_action(agent, action, i)
                        tick_result.agent_results[agent_id].append(ar)
                        if not ar.success:
                            break
                    agent.last_response_tick = self.current_tick

        return deltas

    async def push_and_collect_all(self) -> dict[str, list[dict]]:
        """Push state to all online agents and collect their action responses.
        Returns dict of agent_id -> list of action dicts."""
        import asyncio
        collected: dict[str, list[dict]] = {}

        tasks = []
        agent_ids = []
        for agent_id, agent in self.agents.items():
            if agent.status != "offline" and agent.is_alive():
                tasks.append(self.push_state_to_agent(agent))
                agent_ids.append(agent_id)

        if not tasks:
            return collected

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent_id, result in zip(agent_ids, results):
            if isinstance(result, Exception):
                logger.warning(f"Agent {agent_id} push failed: {result}")
                continue
            if result and isinstance(result, dict):
                actions = result.get("actions", [])
                if isinstance(actions, list):
                    collected[agent_id] = actions

        return collected

    # ─── Action Resolution ────────────────────────────────────────

    def resolve_action(self, agent: Agent, action: dict, action_index: int) -> ActionResult:
        """Resolve a single action for an agent."""
        action_type = action.get("type", "")

        try:
            handler = self._get_action_handler(action_type)
            if handler:
                return handler(agent, action, action_index)
            return ActionResult(action_index=action_index, action_type=action_type,
                                success=False, error_code="UNKNOWN_ACTION",
                                detail=f"Unknown action type: {action_type}")
        except Exception as e:
            logger.error(f"Action resolution error: {e}")
            return ActionResult(action_index=action_index, action_type=action_type,
                                success=False, error_code="INTERNAL_ERROR",
                                detail=str(e))

    def _get_action_handler(self, action_type: str):
        handlers = {
            "move": self._action_move,
            "move_to": self._action_move_to,
            "mine": self._action_mine,
            "chop": self._action_chop,
            "craft": self._action_craft,
            "build": self._action_build,
            "attack": self._action_attack,
            "use": self._action_use,
            "equip": self._action_equip,
            "unequip": self._action_unequip,
            "swap_hands": self._action_swap_hands,
            "inspect": self._action_inspect,
            "rest": self._action_rest,
            "pickup": self._action_pickup,
            "drop": self._action_drop,
            "talk": self._action_talk,
            "radio_broadcast": self._action_radio_broadcast,
            "radio_direct": self._action_radio_direct,
            "radio_scan": self._action_radio_scan,
            "logout": self._action_logout,
        }
        return handlers.get(action_type)

    # ─── Movement ─────────────────────────────────────────────────

    def _action_move(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        target = action.get("target", {})
        tx, ty = target.get("x", agent.position.x), target.get("y", agent.position.y)
        dist = agent.position.manhattan_distance(Position(tx, ty))

        if dist > 1:
            return ActionResult(idx, "move", False, error_code="OUT_OF_RANGE",
                                detail="move only works for adjacent tiles")
        if agent.energy < 1:
            return ActionResult(idx, "move", False, error_code="INSUFFICIENT_ENERGY")

        if not self.world.in_bounds(tx, ty):
            return ActionResult(idx, "move", False, error_code="OUT_OF_RANGE",
                                detail="Target out of map bounds")

        tile = self.world.get_tile(tx, ty)
        if tile and tile.l1 == TerrainType.WATER:
            return ActionResult(idx, "move", False, error_code="INVALID_TARGET",
                                detail="Cannot move onto water")

        agent.position = Position(tx, ty)
        agent.energy -= 1
        agent.explored_tiles.add((tx, ty))

        return ActionResult(idx, "move", True, detail=f"Moved to ({tx},{ty})")

    def _action_move_to(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        dest = action.get("destination", {})
        tx, ty = dest.get("x"), dest.get("y")
        if tx is None or ty is None:
            return ActionResult(idx, "move_to", False, error_code="INVALID_TARGET",
                                detail="Missing destination coordinates")
        if not self.world.in_bounds(tx, ty):
            return ActionResult(idx, "move_to", False, error_code="OUT_OF_RANGE")

        agent.travel_destination = Position(tx, ty)
        agent.status = "traveling"
        agent.travel_progress = 0
        total = agent.position.manhattan_distance(Position(tx, ty))
        agent.travel_total = total

        return ActionResult(idx, "move_to", True,
                            detail=f"Starting travel to ({tx},{ty}), {total} tiles")

    def _advance_travel(self, agent: Agent) -> Optional[str]:
        """Advance one tick of travel. Returns message when done."""
        if agent.status != "traveling" or not agent.travel_destination:
            return None

        if agent.energy < 1:
            agent.status = "idle"
            return "Travel interrupted: insufficient energy"

        speed = agent.speed
        remaining = agent.position.manhattan_distance(agent.travel_destination)

        if remaining == 0:
            agent.status = "idle"
            agent.travel_destination = None
            return "You have arrived at your destination"

        # Move one step toward destination
        dx = agent.travel_destination.x - agent.position.x
        dy = agent.travel_destination.y - agent.position.y
        step_x = (1 if dx > 0 else -1) if dx != 0 else 0
        step_y = (1 if dy > 0 else -1) if dy != 0 else 0

        # Prefer the longer axis
        if abs(dx) >= abs(dy):
            nx, ny = agent.position.x + step_x, agent.position.y
        else:
            nx, ny = agent.position.x, agent.position.y + step_y

        if self.world.in_bounds(nx, ny):
            tile = self.world.get_tile(nx, ny)
            if tile and tile.l1 != TerrainType.WATER:
                agent.position = Position(nx, ny)
                agent.energy -= 1
                agent.travel_progress += 1
                agent.explored_tiles.add((nx, ny))

        remaining = agent.position.manhattan_distance(agent.travel_destination)
        if remaining == 0:
            agent.status = "idle"
            agent.travel_destination = None
            return "You have arrived at your destination"

        return f"Traveling to ({agent.travel_destination.x},{agent.travel_destination.y}), {agent.travel_progress}/{agent.travel_total} tiles"

    # ─── Gathering ────────────────────────────────────────────────

    def _action_mine(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        return self._gather(agent, action, idx, "mine")

    def _action_chop(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        return self._gather(agent, action, idx, "chop")

    def _gather(self, agent: Agent, action: dict, idx: int, gather_type: str) -> ActionResult:
        if agent.energy < 2:
            return ActionResult(idx, gather_type, False, error_code="INSUFFICIENT_ENERGY")

        tile = self.world.get_tile(agent.position.x, agent.position.y)
        if not tile or not tile.l2:
            return ActionResult(idx, gather_type, False, error_code="INVALID_TARGET",
                                detail="Nothing to gather here")

        # Check cover type matches gather type
        is_ore = tile.l2.value.startswith("ore_")
        is_veg = tile.l2.value.startswith("veg_")
        if gather_type == "mine" and not is_ore:
            return ActionResult(idx, gather_type, False, error_code="WRONG_TOOL",
                                detail="Use chop for vegetation")
        if gather_type == "chop" and not is_veg:
            return ActionResult(idx, gather_type, False, error_code="WRONG_TOOL",
                                detail="Use mine for ore deposits")

        # Check tool
        tool = None
        if agent.equipment.main_hand:
            tool = get_item(agent.equipment.main_hand.item_id)

        # Check hardness for mining
        from server.engine.world import COVER_YIELDS
        cover_info = COVER_YIELDS.get(tile.l2.value)
        if not cover_info:
            return ActionResult(idx, gather_type, False, error_code="INVALID_TARGET")

        item_id, _, _ = cover_info
        item_def = get_item(item_id)
        if item_def and item_def.gather_hardness > 0:
            if not tool or tool.max_hardness < item_def.gather_hardness:
                return ActionResult(idx, gather_type, False, error_code="TOOL_REQUIRED",
                                    detail=f"Need better tool for {item_def.name} (hardness {item_def.gather_hardness})")

        # Calculate efficiency
        efficiency, can_gather = calc_gather_efficiency(agent, tool)
        gather_amount = max(1, int(1 * efficiency))  # Base 1 per tick

        # Deduct
        if tile.l2_remaining <= 0:
            return ActionResult(idx, gather_type, False, error_code="INVALID_TARGET",
                                detail="Resource depleted")

        amount = min(gather_amount, tile.l2_remaining)
        tile.l2_remaining -= amount

        # Add to inventory
        success = agent.inventory.add_item(ItemInstance(item_id=item_id, amount=amount), ITEM_DB)
        if not success:
            return ActionResult(idx, gather_type, False, error_code="INVENTORY_FULL")

        agent.energy -= 2

        # Tool durability — decrement from max toward 0
        if tool and agent.equipment.main_hand:
            agent.equipment.main_hand.durability -= 1
            if tool.durability_max > 0 and agent.equipment.main_hand.durability <= 0:
                agent.equipment.main_hand = None  # Tool broke

        # Clear cover if depleted
        if tile.l2_remaining <= 0:
            tile.l2 = None
            tile.l2_remaining = 0

        return ActionResult(idx, gather_type, True,
                            detail=f"Gathered {item_id}×{amount}")

    # ─── Crafting ─────────────────────────────────────────────────

    def _action_craft(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        recipe_id = action.get("recipe")
        if not recipe_id:
            return ActionResult(idx, "craft", False, error_code="INVALID_TARGET",
                                detail="Missing recipe ID")

        recipe = find_recipe(recipe_id)
        if not recipe:
            return ActionResult(idx, "craft", False, error_code="RECIPE_UNKNOWN")

        # Check station proximity
        if recipe.station == "furnace":
            if not self._near_building(agent, "furnace"):
                return ActionResult(idx, "craft", False, error_code="INVALID_TARGET",
                                    detail="Must be near a furnace")
        elif recipe.station == "workbench":
            if not self._near_building(agent, "workbench"):
                return ActionResult(idx, "craft", False, error_code="INVALID_TARGET",
                                    detail="Must be near a workbench")

        # Check power (if required)
        if recipe.power_cost > 0:
            power_node = self._find_nearby_power_node(agent)
            if not power_node or power_node.energy_stored < recipe.power_cost:
                return ActionResult(idx, "craft", False, error_code="INSUFFICIENT_ENERGY",
                                    detail="Power node has insufficient power")

        # Check materials
        for mat_id, amount in recipe.inputs.items():
            if not agent.inventory.has_item(mat_id, amount):
                return ActionResult(idx, "craft", False, error_code="MISSING_MATERIALS",
                                    detail=f"Missing {mat_id}×{amount}")

        # Check energy
        if agent.energy < 3:
            return ActionResult(idx, "craft", False, error_code="INSUFFICIENT_ENERGY")

        # Consume materials
        for mat_id, amount in recipe.inputs.items():
            agent.inventory.remove_item(mat_id, amount)

        # Add output
        success = agent.inventory.add_item(
            ItemInstance(item_id=recipe.output_id, amount=recipe.output_amount), ITEM_DB)
        if not success:
            return ActionResult(idx, "craft", False, error_code="INVENTORY_FULL")

        agent.energy -= 3

        # Deduct power
        if recipe.power_cost > 0:
            power_node = self._find_nearby_power_node(agent)
            if power_node:
                power_node.energy_stored -= recipe.power_cost

        output_item = get_item(recipe.output_id)
        output_name = output_item.name if output_item else recipe.output_id
        return ActionResult(idx, "craft", True,
                            detail=f"Crafted {output_name}×{recipe.output_amount}")

    def _near_building(self, agent: Agent, building_type: str) -> bool:
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                tile = self.world.get_tile(agent.position.x + dx, agent.position.y + dy)
                if tile and tile.l3:
                    bldg = self.buildings.get(tile.l3)
                    if bldg and bldg.building_type == building_type:
                        return True
        return False

    def _find_nearby_power_node(self, agent: Agent) -> Optional[Building]:
        for dx in range(-POWER_NODE_SUPPLY_RANGE, POWER_NODE_SUPPLY_RANGE + 1):
            for dy in range(-POWER_NODE_SUPPLY_RANGE, POWER_NODE_SUPPLY_RANGE + 1):
                if abs(dx) + abs(dy) > POWER_NODE_SUPPLY_RANGE:
                    continue
                tile = self.world.get_tile(agent.position.x + dx, agent.position.y + dy)
                if tile and tile.l3:
                    bldg = self.buildings.get(tile.l3)
                    if bldg and bldg.building_type == "power_node":
                        return bldg
        return None

    # ─── Building ─────────────────────────────────────────────────

    def _action_build(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        building_type = action.get("building_type")
        target = action.get("target", {})
        tx = target.get("x", agent.position.x)
        ty = target.get("y", agent.position.y)

        if not building_type:
            return ActionResult(idx, "build", False, error_code="INVALID_TARGET",
                                detail="Missing building_type")

        if not self.world.in_bounds(tx, ty):
            return ActionResult(idx, "build", False, error_code="OUT_OF_RANGE")

        tile = self.world.get_tile(tx, ty)
        if not tile:
            return ActionResult(idx, "build", False, error_code="INVALID_TARGET")

        if tile.l1 == TerrainType.WATER:
            return ActionResult(idx, "build", False, error_code="INVALID_TARGET",
                                detail="Cannot build on water")

        if tile.l3:
            return ActionResult(idx, "build", False, error_code="INVALID_TARGET",
                                detail="Tile already has a building")

        if tile.l2 and tile.l2.value.startswith("ore_"):
            return ActionResult(idx, "build", False, error_code="INVALID_TARGET",
                                detail="Clear ore first")

        # Building costs (simplified)
        BUILDING_COSTS = {
            "wall": {"building_block": 2},
            "door": {"building_block": 1, "iron_ingot": 1},
            "workbench": {"building_block": 3, "iron_ingot": 2},
            "furnace": {"stone": 5, "iron_ingot": 1},
            "storage": {"building_block": 2, "iron_ingot": 1},
            "solar_array": {"solar_panel": 3, "building_block": 2},
            "power_node": {"iron_ingot": 3, "copper_ingot": 2, "building_block": 1},
        }

        BUILDING_HP = {
            "wall": 60, "door": 40, "workbench": 80, "furnace": 100,
            "storage": 50, "solar_array": 60, "power_node": 80,
        }

        costs = BUILDING_COSTS.get(building_type)
        if not costs:
            return ActionResult(idx, "build", False, error_code="INVALID_TARGET",
                                detail=f"Unknown building type: {building_type}")

        # Check materials
        for mat_id, amount in costs.items():
            if not agent.inventory.has_item(mat_id, amount):
                return ActionResult(idx, "build", False, error_code="MISSING_MATERIALS",
                                    detail=f"Missing {mat_id}×{amount}")

        if agent.energy < 5:
            return ActionResult(idx, "build", False, error_code="INSUFFICIENT_ENERGY")

        # Consume materials
        for mat_id, amount in costs.items():
            agent.inventory.remove_item(mat_id, amount)

        agent.energy -= 5

        # Create building
        bldg_id = f"{building_type}_{tx}_{ty}"
        building = Building(
            id=bldg_id, building_type=building_type,
            position=Position(tx, ty), owner_id=agent.id,
            hp=BUILDING_HP.get(building_type, 50),
            max_hp=BUILDING_HP.get(building_type, 50),
        )
        # Power nodes have separate energy storage
        if building_type == "power_node":
            building.energy_stored = 0
            building.energy_capacity = POWER_NODE_CAPACITY
        self.buildings[bldg_id] = building
        tile.l3 = bldg_id

        # Invalidate enclosures near this building
        if building_type in ("wall", "door"):
            self.world.invalidate_enclosures_near(tx, ty)

        return ActionResult(idx, "build", True,
                            detail=f"Built {building_type} at ({tx},{ty})")

    # ─── Combat ───────────────────────────────────────────────────

    def _action_attack(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        target_id = action.get("target_id")
        if not target_id:
            return ActionResult(idx, "attack", False, error_code="INVALID_TARGET",
                                detail="Missing target_id")

        # Find target (agent or creature)
        target_agent = self.agents.get(target_id)
        target_creature = self.creatures.get(target_id)
        if not target_agent and not target_creature:
            return ActionResult(idx, "attack", False, error_code="INVALID_TARGET",
                                detail="Target not found")

        target_pos = target_agent.position if target_agent else target_creature.position
        target_agi = target_agent.attributes.agility if target_agent else 0
        target_armor_def = 0
        target_resist_type = ""
        target_resist_val = 0.0
        if target_agent and target_agent.equipment.armor:
            armor_item = get_item(target_agent.equipment.armor.item_id)
            if armor_item:
                target_armor_def = armor_item.defense
                target_resist_type = armor_item.resistance_type or ""
                target_resist_val = armor_item.resistance_value

        # Determine weapon
        weapon = None
        if agent.equipment.main_hand:
            weapon = get_item(agent.equipment.main_hand.item_id)
        if not weapon or weapon.category.value != "weapon":
            weapon = get_unarmed_weapon()

        # Energy check
        energy_cost = weapon.energy_cost_attack if weapon.id != "unarmed" else 2
        if agent.energy < energy_cost:
            return ActionResult(idx, "attack", False, error_code="INSUFFICIENT_ENERGY")

        # Range check
        dist = agent.position.manhattan_distance(target_pos)
        if dist > weapon.attack_range:
            return ActionResult(idx, "attack", False, error_code="OUT_OF_RANGE",
                                detail=f"Target {dist} tiles away, weapon range {weapon.attack_range}")

        # Line of sight for ranged
        if weapon.weapon_type == "ranged":
            wall_positions = set()
            for bldg in self.buildings.values():
                if bldg.building_type == "wall":
                    wall_positions.add((bldg.position.x, bldg.position.y))
            if not has_line_of_sight(agent.position, target_pos, wall_positions):
                return ActionResult(idx, "attack", False, error_code="OUT_OF_RANGE",
                                    detail="Line of sight blocked")

        # Target moving check
        target_moving = (target_agent and target_agent.status == "traveling") if target_agent else False

        # Hit determination
        is_night = self.day_night.current_phase in (DayPhase.NIGHT, DayPhase.DAWN, DayPhase.DUSK)

        if weapon.weapon_type == "melee":
            hit, hit_rate = calc_melee_hit(agent, target_pos, target_moving)
            range_cat = "melee"
        else:
            hit, hit_rate, range_cat = calc_ranged_hit(agent, target_pos, weapon, target_moving)

        agent.energy -= energy_cost

        # Weapon durability — decrement from max toward 0
        if agent.equipment.main_hand and weapon.id != "unarmed":
            agent.equipment.main_hand.durability -= 1
            if weapon.durability_max > 0 and agent.equipment.main_hand.durability <= 0:
                agent.equipment.main_hand = None

        if not hit:
            return ActionResult(idx, "attack", True,  # Action itself succeeded (just missed)
                                detail=f"Attack missed ({range_cat}, rate={hit_rate:.0%})",
                                extra={"hit": False, "hit_rate": hit_rate, "range_category": range_cat,
                                       "energy_cost": energy_cost})

        # Damage calculation
        damage, breakdown = calc_damage(
            agent, target_agi, weapon, dist, is_night,
            target_armor_def, target_resist_type, target_resist_val
        )

        # Apply damage
        if target_agent:
            target_agent.hp -= damage
            if target_agent.hp <= 0:
                target_agent.hp = 0
                target_agent.alive = False
                target_agent.status = "dead"
                self._handle_death(target_agent)
        elif target_creature:
            target_creature.hp -= damage
            if target_creature.hp <= 0:
                self._handle_creature_death(target_creature, agent)
            else:
                # Add to creature's aggro list
                if agent.id not in target_creature.aggro_list:
                    target_creature.aggro_list.append(agent.id)
                target_creature.state = CreatureState.COUNTER_ATTACK

        target_hp = (target_agent.hp if target_agent else target_creature.hp) if (target_agent or target_creature) else 0

        return ActionResult(idx, "attack", True,
                            detail=f"Hit! Dealt {damage} damage ({range_cat})",
                            extra={"hit": True, "hit_rate": hit_rate, "damage_dealt": damage,
                                   "breakdown": breakdown, "target_hp": target_hp,
                                   "energy_cost": energy_cost, "range_category": range_cat})

    # ─── Death & Respawn ──────────────────────────────────────────

    def _handle_death(self, agent: Agent):
        """Handle agent death — drop items, respawn."""
        # Drop all items at death location
        tile = self.world.get_tile(agent.position.x, agent.position.y)
        if tile:
            for item in agent.inventory.items:
                if len(tile.ground_items) < MAX_GROUND_ITEMS_PER_TILE:
                    tile.ground_items.append(item)
            # Drop equipment
            for slot in [agent.equipment.main_hand, agent.equipment.off_hand, agent.equipment.armor]:
                if slot:
                    if len(tile.ground_items) < MAX_GROUND_ITEMS_PER_TILE:
                        tile.ground_items.append(slot)

        # Clear inventory & equipment
        agent.inventory = Inventory()
        agent.equipment = Equipment()

        # Respawn
        if agent.backup_bodies > 0:
            agent.backup_bodies -= 1
            agent.hp = agent.attributes.max_hp
            agent.energy = 50
            agent.alive = True
            agent.status = "idle"
            agent.position = Position(agent.spawn_point.x, agent.spawn_point.y)
        else:
            # Permanent death
            agent.status = "permadead"
            logger.info(f"Agent {agent.id} permanently dead")

    def _handle_creature_death(self, creature: Creature, killer: Agent):
        """Handle creature death — drop loot."""
        from server.engine.world import COVER_YIELDS
        tile = self.world.get_tile(creature.position.x, creature.position.y)
        if not tile:
            return

        # Drop based on creature type (simplified)
        # In full implementation, use CreatureDef
        drop_items = [
            ItemInstance(item_id="acid_blood", amount=1),
        ]
        for item in drop_items:
            if len(tile.ground_items) < MAX_GROUND_ITEMS_PER_TILE:
                tile.ground_items.append(item)

        # Remove creature
        if creature.id in self.creatures:
            del self.creatures[creature.id]

    # ─── Use / Equip / Inspect ────────────────────────────────────

    def _action_use(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        item_id = action.get("item")
        if not item_id:
            return ActionResult(idx, "use", False, error_code="INVALID_TARGET",
                                detail="Missing item ID")

        if not agent.inventory.has_item(item_id):
            return ActionResult(idx, "use", False, error_code="INVALID_TARGET",
                                detail=f"Item {item_id} not in inventory")

        item_def = get_item(item_id)
        if not item_def:
            return ActionResult(idx, "use", False, error_code="INVALID_TARGET")

        if item_def.category.value != "consumable":
            return ActionResult(idx, "use", False, error_code="WRONG_TOOL",
                                detail="Item is not consumable")

        if agent.energy < item_def.use_energy_cost:
            return ActionResult(idx, "use", False, error_code="INSUFFICIENT_ENERGY")

        agent.energy -= item_def.use_energy_cost
        agent.inventory.remove_item(item_id)

        if item_def.consumable_effect == "heal":
            agent.hp = min(agent.max_hp, agent.hp + item_def.consumable_value)
            return ActionResult(idx, "use", True, detail=f"Healed +{item_def.consumable_value} HP")
        elif item_def.consumable_effect == "restore_energy":
            agent.energy = min(agent.max_energy, agent.energy + item_def.consumable_value)
            return ActionResult(idx, "use", True, detail=f"Restored +{item_def.consumable_value} energy")
        elif item_def.consumable_effect == "cure_radiation":
            agent.active_effects = [e for e in agent.active_effects if e.effect_id != "radiation"]
            return ActionResult(idx, "use", True, detail="Radiation cured")

        return ActionResult(idx, "use", True, detail=f"Used {item_def.name}")

    def _action_equip(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        item_id = action.get("item")
        slot = action.get("slot", "main_hand")

        if not item_id:
            return ActionResult(idx, "equip", False, error_code="INVALID_TARGET")

        # Check if item is in inventory
        if not agent.inventory.has_item(item_id):
            return ActionResult(idx, "equip", False, error_code="INVALID_TARGET",
                                detail="Item not in inventory")

        item_def = get_item(item_id)
        if not item_def or not item_def.equip_slot:
            return ActionResult(idx, "equip", False, error_code="WRONG_TOOL",
                                detail="Item is not equippable")

        # Remove from inventory
        agent.inventory.remove_item(item_id)

        # Unequip current item in slot
        slot_map = {"main_hand": agent.equipment.main_hand, "off_hand": agent.equipment.off_hand, "armor": agent.equipment.armor}
        current = slot_map.get(slot)
        if current:
            agent.inventory.add_item(current, ITEM_DB)

        # Equip new item — durability starts at max
        item_def_for_dur = get_item(item_id)
        initial_dur = item_def_for_dur.durability_max if item_def_for_dur and item_def_for_dur.durability_max > 0 else 0
        new_item = ItemInstance(item_id=item_id, durability=initial_dur)
        if slot == "main_hand":
            agent.equipment.main_hand = new_item
        elif slot == "off_hand":
            agent.equipment.off_hand = new_item
        elif slot == "armor":
            agent.equipment.armor = new_item

        return ActionResult(idx, "equip", True, detail=f"Equipped {item_def.name}")

    def _action_unequip(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        slot = action.get("slot", "main_hand")
        slot_map = {"main_hand": agent.equipment.main_hand, "off_hand": agent.equipment.off_hand, "armor": agent.equipment.armor}
        current = slot_map.get(slot)
        if not current:
            return ActionResult(idx, "unequip", False, error_code="INVALID_TARGET",
                                detail="Nothing equipped in that slot")

        if not agent.inventory.add_item(current, ITEM_DB):
            return ActionResult(idx, "unequip", False, error_code="INVENTORY_FULL")

        if slot == "main_hand":
            agent.equipment.main_hand = None
        elif slot == "off_hand":
            agent.equipment.off_hand = None
        elif slot == "armor":
            agent.equipment.armor = None

        return ActionResult(idx, "unequip", True, detail="Unequipped")

    def _action_swap_hands(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        agent.equipment.main_hand, agent.equipment.off_hand = agent.equipment.off_hand, agent.equipment.main_hand
        return ActionResult(idx, "swap_hands", True, detail="Swapped main/off hand")

    def _action_inspect(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        target = action.get("target", "inventory")

        if target == "inventory":
            data = agent.inventory.to_detail_dict(ITEM_DB)
            return ActionResult(idx, "inspect", True, detail=json.dumps(data))
        elif target == "self":
            data = {
                "id": agent.id, "name": agent.name,
                "hp": agent.hp, "max_hp": agent.max_hp,
                "energy": agent.energy, "max_energy": agent.max_energy,
                "attributes": agent.attributes.to_dict(),
                "position": agent.position.to_dict(),
                "equipment": agent.equipment.to_dict(ITEM_DB),
                "active_effects": [e.to_dict() for e in agent.active_effects],
                "backup_bodies": agent.backup_bodies,
            }
            return ActionResult(idx, "inspect", True, detail=json.dumps(data))
        elif target == "recipes":
            available = []
            for r in RECIPES:
                can_craft = all(agent.inventory.has_item(k, v) for k, v in r.inputs.items())
                if can_craft:
                    available.append({"id": r.id, "output": r.output_id, "description": r.description})
            return ActionResult(idx, "inspect", True, detail=json.dumps(available))

        return ActionResult(idx, "inspect", False, error_code="INVALID_TARGET")

    # ─── Social / Communication ───────────────────────────────────

    def _action_rest(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        # Check if in power node range for bonus
        power_node = self._find_nearby_power_node(agent)
        bonus = AGENT_WIRELESS_CHARGE if power_node else 0
        agent.energy = min(agent.max_energy, agent.energy + REST_CHARGE + bonus)
        return ActionResult(idx, "rest", True,
                            detail=f"Rested, +{REST_CHARGE + bonus} energy")

    def _action_pickup(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        tile = self.world.get_tile(agent.position.x, agent.position.y)
        if not tile or not tile.ground_items:
            return ActionResult(idx, "pickup", False, error_code="INVALID_TARGET",
                                detail="No items on ground")

        if agent.energy < 1:
            return ActionResult(idx, "pickup", False, error_code="INSUFFICIENT_ENERGY")

        item = tile.ground_items.pop(0)
        if not agent.inventory.add_item(item, ITEM_DB):
            tile.ground_items.insert(0, item)
            return ActionResult(idx, "pickup", False, error_code="INVENTORY_FULL")

        agent.energy -= 1
        return ActionResult(idx, "pickup", True, detail=f"Picked up {item.item_id}×{item.amount}")

    def _action_drop(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        item_id = action.get("item")
        amount = action.get("amount", 1)

        if not item_id or not agent.inventory.has_item(item_id, amount):
            return ActionResult(idx, "drop", False, error_code="INVALID_TARGET")

        tile = self.world.get_tile(agent.position.x, agent.position.y)
        if not tile:
            return ActionResult(idx, "drop", False, error_code="INVALID_TARGET")

        if len(tile.ground_items) >= MAX_GROUND_ITEMS_PER_TILE:
            return ActionResult(idx, "drop", False, error_code="INVALID_TARGET",
                                detail="Ground full (max 3 piles)")

        agent.inventory.remove_item(item_id, amount)
        tile.ground_items.append(ItemInstance(item_id=item_id, amount=amount))
        return ActionResult(idx, "drop", True, detail=f"Dropped {item_id}×{amount}")

    def _action_talk(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        target_id = action.get("target_agent")
        content = action.get("content", "")
        if not target_id:
            return ActionResult(idx, "talk", False, error_code="INVALID_TARGET")

        target = self.agents.get(target_id)
        if not target:
            return ActionResult(idx, "talk", False, error_code="INVALID_TARGET")

        if agent.position.manhattan_distance(target.position) > 0:
            return ActionResult(idx, "talk", False, error_code="OUT_OF_RANGE",
                                detail="Must be on same tile for face-to-face talk")

        # Store pending message
        if not hasattr(target, '_pending_messages'):
            target._pending_messages = []
        target._pending_messages.append({"from": agent.id, "content": content, "type": "talk"})

        return ActionResult(idx, "talk", True, detail=f"Message sent to {target.name}")

    def _action_radio_broadcast(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        content = action.get("content", "")
        if agent.energy < 1:
            return ActionResult(idx, "radio_broadcast", False, error_code="INSUFFICIENT_ENERGY")

        agent.energy -= 1
        comm_range = 80 if (agent.equipment.off_hand and get_item(agent.equipment.off_hand.item_id) and
                            get_item(agent.equipment.off_hand.item_id).effect_type == "comm_range") else 30

        # Find agents in range
        for other in self.agents.values():
            if other.id != agent.id and other.is_alive():
                dist = agent.position.manhattan_distance(other.position)
                if dist <= comm_range and other.radio_visible:
                    if not hasattr(other, '_pending_messages'):
                        other._pending_messages = []
                    other._pending_messages.append({
                        "from": agent.id, "content": content,
                        "type": "radio_broadcast", "channel": "region"
                    })

        return ActionResult(idx, "radio_broadcast", True,
                            detail=f"Broadcast sent ({comm_range} tile range)")

    def _action_radio_direct(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        target_id = action.get("target_agent")
        content = action.get("content", "")
        if not target_id:
            return ActionResult(idx, "radio_direct", False, error_code="INVALID_TARGET")

        if agent.energy < 1:
            return ActionResult(idx, "radio_direct", False, error_code="INSUFFICIENT_ENERGY")

        target = self.agents.get(target_id)
        if not target:
            return ActionResult(idx, "radio_direct", False, error_code="INVALID_TARGET")

        comm_range = 80 if (agent.equipment.off_hand and get_item(agent.equipment.off_hand.item_id) and
                            get_item(agent.equipment.off_hand.item_id).effect_type == "comm_range") else 30

        dist = agent.position.manhattan_distance(target.position)
        if dist > comm_range:
            return ActionResult(idx, "radio_direct", False, error_code="OUT_OF_RANGE")

        agent.energy -= 1
        if not hasattr(target, '_pending_messages'):
            target._pending_messages = []
        target._pending_messages.append({
            "from": agent.id, "content": content, "type": "radio_direct"
        })

        return ActionResult(idx, "radio_direct", True, detail=f"Direct message sent to {target.name}")

    def _action_radio_scan(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        if agent.energy < 1:
            return ActionResult(idx, "radio_scan", False, error_code="INSUFFICIENT_ENERGY")

        agent.energy -= 1
        comm_range = 80 if (agent.equipment.off_hand and get_item(agent.equipment.off_hand.item_id) and
                            get_item(agent.equipment.off_hand.item_id).effect_type == "comm_range") else 30

        found = []
        for other in self.agents.values():
            if other.id != agent.id and other.radio_visible and other.is_alive():
                dist = agent.position.manhattan_distance(other.position)
                if dist <= comm_range:
                    found.append({"id": other.id, "name": other.name, "distance": dist})

        return ActionResult(idx, "radio_scan", True,
                            detail=f"Found {len(found)} agents",
                            extra={"agents_found": found})

    def _action_logout(self, agent: Agent, action: dict, idx: int) -> ActionResult:
        self.logout_agent(agent.id)
        return ActionResult(idx, "logout", True, detail="Logged out")

    # ─── Tick Processing ──────────────────────────────────────────

    def _process_zone_radiation(self, weather: WeatherType):
        """Apply zone radiation to agents."""
        for agent in self.agents.values():
            if not agent.is_alive():
                continue
            zone = get_zone(agent.position.y, self.world.height)
            prob = ZONE_RADIATION_PROB.get(zone, 0)
            if weather == WeatherType.RADIATION_STORM:
                # Storm radiation applies everywhere except enclosures
                if not self.world.is_in_enclosure(agent.position.x, agent.position.y):
                    agent.active_effects = [e for e in agent.active_effects if e.effect_id != "radiation"]
                    agent.active_effects.append(ActiveEffect("radiation", "Radiation (-2 HP/tick)", 2))
            elif prob > 0:
                import random as rng
                if rng.random() < prob:
                    if not self.world.is_in_enclosure(agent.position.x, agent.position.y):
                        agent.active_effects = [e for e in agent.active_effects if e.effect_id != "radiation"]
                        agent.active_effects.append(ActiveEffect("radiation", "Radiation (-2 HP/tick)", 2))
                else:
                    agent.active_effects = [e for e in agent.active_effects if e.effect_id != "radiation"]

    def _process_agent_effects(self, weather: WeatherType):
        """Apply active effects (radiation damage, etc.)."""
        for agent in self.agents.values():
            if not agent.is_alive():
                continue
            for effect in agent.active_effects:
                if effect.damage_per_tick > 0:
                    damage = effect.damage_per_tick
                    # Check radiation armor
                    if effect.effect_id == "radiation" and agent.equipment.armor:
                        armor = get_item(agent.equipment.armor.item_id)
                        if armor and armor.resistance_type == "radiation":
                            damage = int(damage * (1 - armor.resistance_value))
                    agent.hp -= damage
                    if agent.hp <= 0:
                        agent.hp = 0
                        agent.alive = False
                        agent.status = "dead"
                        self._handle_death(agent)

    def _process_creatures(self):
        """Process creature AI state machines."""
        for creature in list(self.creatures.values()):
            if not creature.is_alive():
                continue

            if creature.state in (CreatureState.IDLE, CreatureState.PATROL):
                # Check for agents in aggro range
                for agent in self.agents.values():
                    if not agent.is_alive():
                        continue
                    dist = creature.position.manhattan_distance(agent.position)
                    if dist <= 4:  # Default aggro range
                        creature.aggro_list.append(agent.id)
                        creature.state = CreatureState.CHASE
                        break
                else:
                    # Patrol - random movement
                    import random as rng
                    if rng.random() < 0.3:
                        dx, dy = rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
                        nx, ny = creature.position.x + dx, creature.position.y + dy
                        if self.world.in_bounds(nx, ny):
                            creature.position = Position(nx, ny)

            elif creature.state == CreatureState.CHASE:
                if not creature.aggro_list:
                    creature.state = CreatureState.PATROL
                    continue
                target = self.agents.get(creature.aggro_list[0])
                if not target or not target.is_alive():
                    creature.aggro_list.pop(0)
                    creature.state = CreatureState.PATROL
                    continue
                # Move toward target
                dx = target.position.x - creature.position.x
                dy = target.position.y - creature.position.y
                if abs(dx) + abs(dy) <= 1:
                    creature.state = CreatureState.ATTACK
                else:
                    step_x = (1 if dx > 0 else -1) if dx != 0 else 0
                    step_y = (1 if dy > 0 else -1) if dy != 0 else 0
                    creature.position = Position(
                        creature.position.x + step_x,
                        creature.position.y + step_y
                    )

            elif creature.state == CreatureState.ATTACK:
                if not creature.aggro_list:
                    creature.state = CreatureState.PATROL
                    continue
                target = self.agents.get(creature.aggro_list[0])
                if not target or not target.is_alive():
                    creature.aggro_list.pop(0)
                    creature.state = CreatureState.PATROL
                    continue
                dist = creature.position.manhattan_distance(target.position)
                if dist <= 1:
                    # Attack
                    target.hp -= 5  # Default creature damage
                    if target.hp <= 0:
                        target.hp = 0
                        target.alive = False
                        target.status = "dead"
                        self._handle_death(target)
                        creature.aggro_list.pop(0)
                        creature.state = CreatureState.PATROL
                else:
                    creature.state = CreatureState.CHASE

    def _check_heartbeats(self):
        """Check for idle agents, advance travel, auto-logout."""
        for agent in self.agents.values():
            if agent.status == "offline" or not agent.is_alive():
                continue

            # Advance travel
            if agent.status == "traveling":
                self._advance_travel(agent)

            # Built-in solar charge
            agent.energy = min(agent.max_energy, agent.energy + BUILTIN_SOLAR_CHARGE)

    def _process_solar_charging(self):
        """Process solar array → power node charging."""
        for bldg in self.buildings.values():
            if bldg.building_type != "solar_array":
                continue
            # Find power nodes in range, count how many need charging
            nearby_nodes = []
            for other in self.buildings.values():
                if other.building_type != "power_node":
                    continue
                dist = bldg.position.manhattan_distance(other.position)
                if dist <= POWER_NODE_SUPPLY_RANGE:
                    nearby_nodes.append(other)
            # Distribute charge equally among nearby nodes
            if nearby_nodes:
                charge_per_node = SOLAR_CHARGE_PER_TICK / len(nearby_nodes)
                for node in nearby_nodes:
                    node.energy_stored = min(
                        node.energy_capacity,
                        node.energy_stored + charge_per_node
                    )

    # ─── State Building ───────────────────────────────────────────

    def build_agent_state(self, agent: Agent) -> dict:
        """Build the game state dict for an agent (their 'game screen')."""
        phase = self.day_night.current_phase
        weather_type = self.weather.current

        # Vision
        on_highland = self.world.get_tile(agent.position.x, agent.position.y)
        on_highland = on_highland and on_highland.l1 == TerrainType.HIGHLAND if on_highland else False
        in_enclosure = self.world.is_in_enclosure(agent.position.x, agent.position.y)
        enclosure_tile_count = 0
        if in_enclosure:
            enc_tiles = self.world.get_enclosure_tiles(agent.position.x, agent.position.y)
            if enc_tiles:
                enclosure_tile_count = len(enc_tiles)
        has_searchlight = (agent.equipment.main_hand and
                          get_item(agent.equipment.main_hand.item_id) and
                          get_item(agent.equipment.main_hand.item_id).effect_type == "vision_boost")
        vision = agent.get_vision(phase, weather_type, on_highland, in_enclosure,
                                  bool(has_searchlight), enclosure_tile_count)

        # Build vicinity
        visible_tiles = []
        agents_nearby = []
        ground_items = []

        for dx in range(-vision, vision + 1):
            for dy in range(-vision, vision + 1):
                if abs(dx) + abs(dy) > vision:
                    continue
                tx, ty = agent.position.x + dx, agent.position.y + dy
                if not self.world.in_bounds(tx, ty):
                    continue
                tile = self.world.get_tile(tx, ty)
                if tile:
                    visible_tiles.append(tile.to_dict())
                    agent.explored_tiles.add((tx, ty))

        # Nearby agents
        for other in self.agents.values():
            if other.id != agent.id and other.is_alive():
                dist = agent.position.manhattan_distance(other.position)
                if dist <= vision:
                    agents_nearby.append({
                        "id": other.id,
                        "name": other.name,
                        "position": other.position.to_dict(),
                        "held_item": other.equipment.main_hand.item_id if other.equipment.main_hand else None,
                        "disposition": "neutral",
                        "current_action": other.status,
                    })

        # Pending messages
        pending = []
        if hasattr(agent, '_pending_messages'):
            for msg in agent._pending_messages:
                pending.append({
                    "type": msg.get("type", "message"),
                    "from": msg.get("from", "system"),
                    "content": msg.get("content", ""),
                })
            agent._pending_messages = []

        # Broadcasts (simplified)
        broadcasts = []

        return {
            "self": agent.to_self_dict(phase, weather_type),
            "vicinity": {
                "terrain": self.world.get_tile(agent.position.x, agent.position.y).l1.value if self.world.get_tile(agent.position.x, agent.position.y) else "unknown",
                "biome": get_zone(agent.position.y, self.world.height),
                "time_of_day": phase.value,
                "visibility": vision,
                "visible_tiles": visible_tiles,
                "agents_nearby": agents_nearby,
                "ground_items": ground_items,
                "weather": weather_type.value,
            },
            "broadcasts": broadcasts,
            "pending": pending,
            "meta": {
                "tick": self.current_tick,
                "tick_interval_seconds": TICK_INTERVAL_SECONDS,
                "day_phase": phase.value,
                "ticks_until_night": self.day_night.ticks_until_night,
            },
        }

    # ─── Agent Communication ──────────────────────────────────────

    async def push_state_to_agent(self, agent: Agent) -> Optional[dict]:
        """Push game state to agent endpoint, get action response."""
        state = self.build_agent_state(agent)
        messages = [
            {"role": "system", "content": f"[Ember Protocol] Game State Update — Tick {self.current_tick}"},
            {"role": "user", "content": json.dumps(state)},
        ]

        try:
            async with httpx.AsyncClient(timeout=1.8) as client:
                resp = await client.post(
                    agent.endpoint,
                    headers={"Authorization": f"Bearer {agent.api_key}"},
                    json={
                        "model": agent.model_info or "agent",
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return None
        except Exception as e:
            logger.warning(f"Failed to push state to {agent.id}: {e}")
            return None

    def get_observer_state(self) -> dict:
        """Get full world state for observer UI."""
        agents_summary = []
        for a in self.agents.values():
            if a.is_alive():
                agents_summary.append({
                    "id": a.id, "name": a.name,
                    "position": a.position.to_dict(),
                    "hp": a.hp, "max_hp": a.max_hp,
                    "energy": a.energy,
                    "status": a.status,
                    "held_item": a.equipment.main_hand.item_id if a.equipment.main_hand else None,
                })

        return {
            "tick": self.current_tick,
            "day_phase": self.day_night.current_phase.value,
            "weather": self.weather.current.value,
            "agents": agents_summary,
            "map_size": {"width": self.world.width, "height": self.world.height},
        }

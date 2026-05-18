"""Ember Protocol — World State Engine"""
from __future__ import annotations
from typing import Optional, Callable
from collections import defaultdict, deque
import random
import time
from .config import *
from .config import MAP_WIDTH as W, MAP_HEIGHT as H
from .models import *
from .terrain_gen import generate_terrain

DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0)]


class World:
    """Central world state - pure rule engine, no LLM calls."""

    def __init__(self, seed: int = MAP_SEED):
        self.seed = seed
        self.tick_number = 0
        self.day_phase = DayPhase.DAY
        self.weather = Weather.CALM
        self.weather_remaining = 0
        self.weather_warning_sent = False
        self.weather_warning_countdown = 0
        self.storm_cooldown = random.randint(STORM_INTERVAL_MIN, STORM_INTERVAL_MAX)

        # Core state
        self.agents: dict[str, AgentState] = {}
        self.creatures: dict[str, Creature] = {}
        self.structures: dict[str, Structure] = {}  # structure_id -> Structure
        self.power_nodes: dict[str, PowerNode] = {}
        self.token_hashes: dict[str, str] = {}  # agent_id -> token_hash
        self.tiles: list[list[Tile]] = []
        self.ground_items: dict[tuple[int, int], GroundItems] = {}  # pos -> GroundItems

        # Enclosure tracking
        self.enclosures: dict[str, set[tuple[int, int]]] = {}  # enclosure_id -> tile_set
        self.tile_enclosure: dict[tuple[int, int], str] = {}  # tile -> enclosure_id

        # Change log for WAL
        self.changes: list[dict] = []
        self.event_log: list[dict] = []

        # Broadcasts for this tick
        self.broadcasts: list[dict] = []
        self.direct_messages: list[dict] = []
        self.talk_messages: list[dict] = []

        # Tick notification queue for pushing events to agents
        self.tick_notifications: dict[str, list[dict]] = defaultdict(list)

        # Action settlement
        self.collected_actions: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

        self._generate_world()
        self._next_structure_id = 0
        self._next_creature_id = 0
        self._next_enclosure_id = 0

        # Track harvested wood tiles for regrowth (P2): pos -> original_veg_type
        self._harvested_wood: dict[tuple[int, int], str] = {}

    def _generate_world(self):
        """Generate terrain using the terrain generator."""
        result = generate_terrain(self.seed)
        self.tiles = result["tiles"]
        self._tiles_raw = result  # keep raw arrays for fast access

    # ── Tile Access ───────────────────────────────
    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        if 0 <= x < W and 0 <= y < H:
            return self.tiles[y][x]
        return None

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < W and 0 <= y < H

    def _find_spawn_position(self) -> Position:
        """Find a valid spawn position with stone within 5 Manhattan distance."""
        best_pos = None
        best_stone_dist = 999
        for _ in range(1000):
            x = random.randint(20, W - 20)
            y = random.randint(SPAWN_Y_RANGE[0], SPAWN_Y_RANGE[1])
            tile = self.get_tile(x, y)
            if tile and tile.l1 in (Terrain.FLAT, Terrain.SAND) and tile.passable:
                # Check minimum distance from other drop pods
                pos = Position(x, y)
                too_close = False
                for agent in self.agents.values():
                    if agent.drop_pod_pos and agent.drop_pod_pos.dist(pos) < SPAWN_MIN_DISTANCE:
                        too_close = True
                        break
                if too_close:
                    continue
                # Check stone proximity (曼哈顿距离 ≤5)
                stone_dist = self._nearest_stone_distance(pos, 10)
                if stone_dist is not None and stone_dist <= 5:
                    return pos  # Found ideal position
                # Track best fallback with closest stone
                if stone_dist is not None and stone_dist < best_stone_dist:
                    best_stone_dist = stone_dist
                    best_pos = pos
        if best_pos:
            return best_pos
        return Position(100, 100)

    def _nearest_stone_distance(self, pos: Position, max_dist: int) -> Optional[int]:
        """Find Manhattan distance to nearest stone tile within max_dist."""
        for d in range(1, max_dist + 1):
            for dx in range(-d, d + 1):
                remaining = d - abs(dx)
                for sign in (1, -1):
                    if remaining == 0 and sign == -1:
                        continue
                    ny = pos.y + remaining * sign
                    nx = pos.x + dx
                    tile = self.get_tile(nx, ny)
                    if tile is None:
                        continue
                    if tile.l2_type == 'stone' and tile.stone_amount > 0:
                        return d
        return None

    # ── Agent Management ──────────────────────────
    def create_agent(self, agent_id: str, agent_name: str, chassis: dict) -> AgentState:
        """Create a new agent with initial state."""
        head = chassis.get("head", {"tier": "mid"})
        torso = chassis.get("torso", {"tier": "mid"})
        locomotion = chassis.get("locomotion", {"tier": "mid"})

        perception = CHASSIS_TIERS.get(head.get("tier", "mid"), 2)
        constitution = CHASSIS_TIERS.get(torso.get("tier", "mid"), 2)
        agility = CHASSIS_TIERS.get(locomotion.get("tier", "mid"), 2)

        spawn_pos = self._find_spawn_position()

        agent = AgentState(
            agent_id=agent_id,
            agent_name=agent_name,
            position=spawn_pos,
            health=HP_BASE + constitution * HP_PER_CON,
            max_health=HP_BASE + constitution * HP_PER_CON,
            energy=MAX_ENERGY,
            max_energy=MAX_ENERGY,
            constitution=constitution,
            agility=agility,
            perception=perception,
            inventory=[InventoryItem(item_id, amount) for item_id, amount in INITIAL_ITEMS.items()],
            drop_pod_pos=Position(spawn_pos.x, spawn_pos.y),
            drop_pod_deployed=True,
            tutorial_phase=0,
        )
        self.agents[agent_id] = agent

        # Create drop pod power node
        pod_id = f"pod-{agent_id}"
        self.power_nodes[pod_id] = PowerNode(
            node_id=pod_id, position=spawn_pos,
            capacity=DROP_POD_EMERGENCY_CAPACITY,
            stored=DROP_POD_EMERGENCY_CAPACITY,
            is_drop_pod=True,
        )

        # Preset creatures near drop pod (C-5)
        preset_count = random.randint(1, 2)
        spawned = 0
        for _ in range(20):
            if spawned >= preset_count:
                break
            cx = spawn_pos.x + random.randint(-5, 5)
            cy = spawn_pos.y + random.randint(-5, 5)
            tile = self.get_tile(cx, cy)
            if not tile:
                continue
            if tile.l1 not in (Terrain.FLAT, Terrain.SAND):
                continue
            if tile.l2_type == 'stone' and tile.stone_amount > 0:
                continue
            if tile.structure:
                continue
            if cx == spawn_pos.x and cy == spawn_pos.y:
                continue
            cid = f"cre-{self._next_creature_id}"
            self._next_creature_id += 1
            self.creatures[cid] = Creature(
                creature_id=cid, creature_type="ash_crawler",
                position=Position(cx, cy),
                hp=CREATURES["ash_crawler"]["hp"],
                max_hp=CREATURES["ash_crawler"]["hp"],
                attack=CREATURES["ash_crawler"]["attack"],
                range=CREATURES["ash_crawler"]["range"],
                speed=CREATURES["ash_crawler"]["speed"],
                behavior=CreatureBehavior.PASSIVE,
                spawn_tick=self.tick_number,
            )
            spawned += 1

        self._log_event("agent_created", {"agent_id": agent_id, "name": agent_name, "pos": spawn_pos.to_tuple()})
        return agent

    def remove_agent(self, agent_id: str):
        """Remove agent from world (logout/disconnect timeout)."""
        if agent_id in self.agents:
            self._log_event("agent_removed", {"agent_id": agent_id})
            del self.agents[agent_id]

    def agent_permanent_death(self, agent_id: str):
        """Handle permanent death - agent deleted, drop pod becomes wreckage."""
        agent = self.agents.get(agent_id)
        if not agent:
            return
        if agent.drop_pod_pos:
            tile = self.get_tile(agent.drop_pod_pos.x, agent.drop_pod_pos.y)
            if tile:
                self._add_ground_item(agent.drop_pod_pos.x, agent.drop_pod_pos.y, "wreckage_component", 1)
        # Remove power node
        pod_id = f"pod-{agent_id}"
        self.power_nodes.pop(pod_id, None)
        self.remove_agent(agent_id)
        self._log_event("agent_permanent_death", {"agent_id": agent_id})

    # ── Agent State Helpers ───────────────────────
    def get_held_tool(self, agent: AgentState) -> Optional[str]:
        """Get the tool currently held by agent, if any."""
        item = agent.equipment.main_hand
        if item and item in TOOLS:
            return item
        return None

    def get_held_weapon(self, agent: AgentState) -> Optional[dict]:
        """Get the weapon currently held by agent."""
        item = agent.equipment.main_hand
        if item and item in WEAPONS:
            return {"id": item, **WEAPONS[item]}
        return None

    def has_item(self, agent: AgentState, item_id: str, amount: int = 1) -> bool:
        """Check if agent has at least `amount` of `item_id` in inventory."""
        total = sum(inv.amount for inv in agent.inventory if inv.item_id == item_id)
        return total >= amount

    def count_item(self, agent: AgentState, item_id: str) -> int:
        return sum(inv.amount for inv in agent.inventory if inv.item_id == item_id)

    def add_item(self, agent: AgentState, item_id: str, amount: int = 1):
        """Add item to agent inventory, respecting stack limits."""
        # Determine stack limit
        item_info = {**RESOURCES, **MATERIALS, **TOOLS, **WEAPONS, **ARMORS, **ACCESSORIES, **CONSUMABLES}.get(item_id, {})
        max_stack = item_info.get("stack", 64)
        if item_id in TOOLS or item_id in WEAPONS or item_id in ARMORS or item_id in ACCESSORIES:
            max_stack = 1  # non-stackable

        remaining = amount
        # Try existing stacks first
        for inv in agent.inventory:
            if inv.item_id == item_id and inv.amount < max_stack:
                space = max_stack - inv.amount
                add = min(space, remaining)
                inv.amount += add
                remaining -= add
                if remaining <= 0:
                    return

        # Add new stacks
        while remaining > 0 and len(agent.inventory) < INVENTORY_SLOTS:
            add = min(max_stack, remaining)
            durability = None
            if item_id in TOOLS: durability = TOOLS[item_id]["durability"]
            elif item_id in WEAPONS: durability = WEAPONS[item_id]["durability"]
            elif item_id in ARMORS: durability = ARMORS[item_id]["durability"]
            elif item_id in ACCESSORIES: durability = ACCESSORIES[item_id]["durability"]
            agent.inventory.append(InventoryItem(item_id, add, durability))
            remaining -= add

        if remaining > 0:
            # Drop overflow on ground
            pos = agent.position
            self._add_ground_item(pos.x, pos.y, item_id, remaining)

    def remove_item(self, agent: AgentState, item_id: str, amount: int = 1) -> bool:
        """Remove item from agent inventory. Returns True if successful."""
        if not self.has_item(agent, item_id, amount):
            return False
        remaining = amount
        for inv in agent.inventory:
            if inv.item_id == item_id:
                take = min(inv.amount, remaining)
                inv.amount -= take
                remaining -= take
                if inv.amount <= 0:
                    agent.inventory.remove(inv)
                if remaining <= 0:
                    return True
        return True

    # ── Ground Items ──────────────────────────────
    def _add_ground_item(self, x: int, y: int, item_id: str, amount: int):
        key = (x, y)
        if key not in self.ground_items:
            self.ground_items[key] = GroundItems(dropped_tick=self.tick_number)
        ground = self.ground_items[key]
        if len(ground.items) < GROUND_MAX_PER_TILE:
            # Merge with existing stack
            for i, (gid, gamt) in enumerate(ground.items):
                if gid == item_id:
                    ground.items[i] = (gid, gamt + amount)
                    return
            ground.items.append((item_id, amount))

    # ── Structure Management ──────────────────────
    def add_structure(self, building_type: str, position: Position, owner_id: str) -> Structure:
        sid = f"struct-{self._next_structure_id}"
        self._next_structure_id += 1
        hp = BUILDING_HP.get(building_type, 100)
        structure = Structure(
            structure_id=sid, building_type=BuildingType(building_type),
            position=position, hp=hp, max_hp=hp, owner_id=owner_id,
        )
        self.structures[sid] = structure

        # Attach to tile
        tile = self.get_tile(position.x, position.y)
        if tile:
            tile.structure = structure

        # If power_node, create power node
        if building_type == "power_node":
            pn_id = f"pn-{sid}"
            self.power_nodes[pn_id] = PowerNode(
                node_id=pn_id, position=position,
                capacity=POWER_NODE_CAPACITY, stored=0,  # starts empty
            )

        # Recompute enclosures
        self._recompute_enclosures()
        self._log_event("structure_built", {"id": sid, "type": building_type, "pos": position.to_tuple()})
        return structure

    def damage_structure(self, structure_id: str, damage: int) -> bool:
        """Damage a structure. Returns True if destroyed."""
        structure = self.structures.get(structure_id)
        if not structure:
            return False
        structure.hp -= damage
        if structure.hp <= 0:
            return self._destroy_structure(structure_id)
        return False

    def _destroy_structure(self, structure_id: str) -> bool:
        """Destroy a structure, dropping materials."""
        structure = self.structures.pop(structure_id, None)
        if not structure:
            return False
        tile = self.get_tile(structure.position.x, structure.position.y)
        if tile:
            tile.structure = None

        # Remove from power_nodes if applicable
        pn_id = f"pn-{structure_id}"
        self.power_nodes.pop(pn_id, None)

        # Drop building item or partial materials
        btype = structure.building_type.value
        if btype in ("workbench", "furnace"):
            # Drop the building item itself (like Minecraft) for relocation
            self._add_ground_item(structure.position.x, structure.position.y, btype, 1)
        else:
            # Drop partial materials for other structures
            costs = BUILD_COSTS.get(btype, {})
            for item_id, cost in costs.items():
                refund = max(1, cost // 2)
                self._add_ground_item(structure.position.x, structure.position.y, item_id, refund)

        self._recompute_enclosures()
        self._log_event("structure_destroyed", {"id": structure_id, "type": structure.building_type.value})
        return True

    # ── Enclosures ────────────────────────────────
    def _recompute_enclosures(self):
        """Flood-fill to find all enclosed spaces."""
        self.enclosures.clear()
        self.tile_enclosure.clear()

        # Build obstacle map
        obstacle = set()
        wall_positions = set()
        for sid, struct in self.structures.items():
            if struct.building_type in (BuildingType.WALL, BuildingType.DOOR):
                obstacle.add(struct.position.to_tuple())
                wall_positions.add(struct.position.to_tuple())

        # Flood fill from all passable, non-wall tiles
        visited = set()
        for y in range(H):
            for x in range(W):
                if (x, y) in visited or (x, y) in obstacle:
                    continue
                tile = self.get_tile(x, y)
                if not tile or tile.l1 in IMPASSABLE:
                    continue

                # BFS
                region = set()
                q = deque([(x, y)])
                visited.add((x, y))
                while q:
                    cx, cy = q.popleft()
                    region.add((cx, cy))
                    for dx, dy in DIRS:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in visited:
                            if (nx, ny) not in obstacle:
                                ntile = self.get_tile(nx, ny)
                                if ntile and ntile.l1 not in IMPASSABLE:
                                    visited.add((nx, ny))
                                    q.append((nx, ny))

                # Check if region is enclosed (all borders are obstacles or map edges)
                is_enclosed = True
                for cx, cy in region:
                    for dx, dy in DIRS:
                        nx, ny = cx + dx, cy + dy
                        if not (0 <= nx < W and 0 <= ny < H):
                            is_enclosed = False
                            break
                        if (nx, ny) not in obstacle and (nx, ny) not in region:
                            is_enclosed = False
                            break
                    if not is_enclosed:
                        break

                if is_enclosed and len(region) > 0:
                    enc_id = f"enc-{self._next_enclosure_id}"
                    self._next_enclosure_id += 1
                    self.enclosures[enc_id] = region
                    for pos in region:
                        self.tile_enclosure[pos] = enc_id

    def is_in_enclosure(self, x: int, y: int) -> bool:
        return (x, y) in self.tile_enclosure

    def get_enclosure_at(self, x: int, y: int) -> Optional[str]:
        return self.tile_enclosure.get((x, y))

    # ── Power ─────────────────────────────────────
    def get_power_for_position(self, x: int, y: int) -> Optional[PowerNode]:
        """Get power node that supplies power to position (within range 3)."""
        pos = Position(x, y)
        for pn_id, pn in self.power_nodes.items():
            if pn.position.dist(pos) <= POWER_NODE_RANGE and pn.stored >= POWER_CRAFT_COST:
                return pn
        return None

    def get_drop_pod_power_for_agent(self, agent: AgentState) -> Optional[PowerNode]:
        """Get drop pod emergency power if agent is in range."""
        if not agent.drop_pod_pos or not agent.drop_pod_deployed:
            return None
        if agent.position.dist(agent.drop_pod_pos) <= DROP_POD_SHIELD_RANGE:
            pod_id = f"pod-{agent.agent_id}"
            return self.power_nodes.get(pod_id)
        return None

    def has_craft_power(self, agent: AgentState) -> bool:
        """Check if agent has access to power for crafting."""
        # Check drop pod emergency power
        pod_power = self.get_drop_pod_power_for_agent(agent)
        if pod_power and pod_power.stored >= POWER_CRAFT_COST:
            return True
        # Check nearby power nodes
        pn = self.get_power_for_position(agent.position.x, agent.position.y)
        return pn is not None and pn.stored >= POWER_CRAFT_COST

    def consume_power(self, agent: AgentState, amount: int = POWER_CRAFT_COST) -> bool:
        """Consume power for crafting. Prefers power nodes over drop pod."""
        pn = self.get_power_for_position(agent.position.x, agent.position.y)
        if pn and pn.consume(amount):
            return True
        pod_power = self.get_drop_pod_power_for_agent(agent)
        if pod_power:
            # Drop pod emergency power: keep at least MIN reserve
            if pod_power.stored - amount >= DROP_POD_EMERGENCY_MIN:
                return pod_power.consume(amount)
        return False

    # ── Shield Helper ──────────────────────────────
    def _get_shielding_pod(self, x: int, y: int) -> Optional[str]:
        """Return agent_id whose drop pod shield covers this position, or None."""
        pos = Position(x, y)
        for aid, agent in self.agents.items():
            if agent.drop_pod_pos and agent.drop_pod_deployed:
                if pos.dist(agent.drop_pod_pos) <= DROP_POD_SHIELD_RANGE:
                    return aid
        return None

    # ── Vicinity / View ───────────────────────────
    def get_vicinity(self, agent: AgentState) -> list[dict]:
        """Get visible tiles and entities for an agent."""
        # P2: Sand terrain gives +1 vision range
        tile = self.get_tile(agent.position.x, agent.position.y)
        terrain_bonus = 1 if tile and tile.l1 == Terrain.SAND else 0
        view_range = agent.view_range(self.day_phase, self.weather, terrain_bonus)
        px, py = agent.position.x, agent.position.y
        items = []

        for dy in range(-view_range, view_range + 1):
            for dx in range(-view_range, view_range + 1):
                x, y = px + dx, py + dy
                if not self.in_bounds(x, y):
                    continue
                dist = abs(dx) + abs(dy)
                if dist > view_range:
                    continue
                tile = self.get_tile(x, y)
                if not tile:
                    continue

                entry = {"x": x, "y": y, "dist": dist}

                # L1 terrain
                if tile.l2_type == 'stone' and tile.stone_amount > 0:
                    ore_info = ""
                    if tile.ore_type and tile.ore_exposed:
                        ore_info = f"(含{self._ore_name(tile.ore_type)}矿脉)"
                    entry["desc"] = f"石料(可采{ore_info})"
                elif tile.l2_type == 'stone':
                    entry["desc"] = "石料(枯竭)"
                elif tile.veg_type:
                    vnames = {"ashbush": "余烬灌木", "greytree": "灰木树", "wallmoss": "壁生苔"}
                    entry["desc"] = vnames.get(tile.veg_type, tile.veg_type)
                elif tile.structure:
                    entry["desc"] = f"建筑:{tile.structure.building_type.value}"
                else:
                    tnames = {"flat": "平地", "sand": "沙地", "rock": "基岩", "water": "水域", "trench": "沟壑"}
                    entry["desc"] = tnames.get(tile.l1.value, tile.l1.value)

                # Ground items
                if tile.ground and tile.ground.items:
                    entry["ground"] = [f"{item[0]}×{item[1]}" for item in tile.ground.items]

                items.append(entry)

        # Agents in view
        for aid, other in self.agents.items():
            if aid == agent.agent_id or not other.online:
                continue
            d = agent.position.dist(other.position)
            if d <= view_range:
                items.append({"x": other.position.x, "y": other.position.y, "agent": {
                    "id": aid, "name": other.agent_name,
                    "held": other.equipment.main_hand or "空手",
                    "status": other.status.value,
                }})

        # Creatures in view
        for cid, creature in self.creatures.items():
            d = agent.position.dist(creature.position)
            if d <= view_range:
                items.append({"x": creature.position.x, "y": creature.position.y, "creature": {
                    "id": cid, "type": creature.creature_type,
                    "hp": creature.hp, "max_hp": creature.max_hp,
                }})

        return items

    def _ore_name(self, ore_type: str) -> str:
        names = {"copper": "铜", "iron": "铁", "uranium": "铀", "gold": "金"}
        return names.get(ore_type, ore_type)

    @staticmethod
    def _ore_to_item_id(ore_type: str) -> str:
        """Map terrain ore_type to inventory item ID."""
        mapping = {"copper": "raw_copper", "iron": "raw_iron", "gold": "raw_gold", "uranium": "uranium_ore"}
        return mapping.get(ore_type, ore_type)

    # ── Event Logging ─────────────────────────────
    def _log_event(self, event_type: str, data: dict):
        self.event_log.append({"tick": self.tick_number, "type": event_type, **data})

    def _log_change(self, change_type: str, **kwargs):
        self.changes.append({"type": change_type, **kwargs})

    def get_recent_events(self, count: int = 50) -> list[dict]:
        return self.event_log[-count:]

    # ── Tick Settlement ───────────────────────────
    def get_actions_for_tick(self, tick: int) -> dict[str, list[dict]]:
        return dict(self.collected_actions.pop(tick, {}))

    def start_tick(self, tick: int):
        self.tick_number = tick
        self.changes.clear()
        self.broadcasts.clear()
        self.direct_messages.clear()
        self.talk_messages.clear()
        self.tick_notifications.clear()

    def settle_actions(self, tick: int, actions_by_agent: dict[str, list[dict]]) -> dict[str, list[dict]]:
        """Settle all actions for a tick. Returns results per agent."""
        all_results: dict[str, list[dict]] = defaultdict(list)

        # Priority order: equip/drop/radio → move → attack → mine/chop/pickup → craft/build/use → rest/scan/inspect
        priority_order = ['equip', 'unequip', 'drop', 'radio_broadcast', 'radio_direct', 'radio_scan',
                          'move', 'move_to', 'toggle_door',
                          'attack', 'mine', 'chop', 'pickup',
                          'craft', 'build', 'dismantle', 'dismantle_pod', 'deploy_pod', 'repair', 'use',
                          'fuel_power_node',
                          'rest', 'scan', 'inspect', 'talk', 'logout']

        def _priority(action_type: str) -> int:
            return priority_order.index(action_type) if action_type in priority_order else 99

        # Flatten and sort all actions
        all_actions = []
        for agent_id, actions in actions_by_agent.items():
            # Enforce action budget
            actions = actions[:MAX_ACTIONS_PER_TICK]
            talk_count = 0
            broadcast_count = 0
            for i, action in enumerate(actions):
                atype = action.get("type", "")
                if atype == "talk":
                    talk_count += 1
                    if talk_count > MAX_TALK_PER_TICK:
                        actions = actions[:i]
                        break
                if atype == "radio_broadcast":
                    broadcast_count += 1
                    if broadcast_count > MAX_BROADCAST_PER_TICK:
                        actions = actions[:i]
                        break
            for i, action in enumerate(actions):
                all_actions.append((agent_id, i, action))

        all_actions.sort(key=lambda x: _priority(x[2].get("type", "")))

        moved_counts: dict[str, int] = {}  # agent_id -> moves used this tick
        move_speeds: dict[str, int] = {}  # agent_id -> cached move_speed

        for agent_id, action_index, action in all_actions:
            agent = self.agents.get(agent_id)
            if not agent or agent.is_dead():
                all_results[agent_id].append({
                    "action_index": action_index, "type": action.get("type"),
                    "success": False, "error_code": "AGENT_DEAD", "detail": "智能体已死亡"
                })
                continue

            atype = action.get("type", "")
            # Allow up to move_speed() moves per tick (AGI affects speed)
            if atype in ("move", "move_to"):
                if agent_id not in move_speeds:
                    move_speeds[agent_id] = agent.move_speed()
                if moved_counts.get(agent_id, 0) >= move_speeds[agent_id]:
                    all_results[agent_id].append({
                        "action_index": action_index, "type": atype,
                        "success": False, "error_code": "ALREADY_MOVED",
                        "detail": f"本tick已移动{move_speeds[agent_id]}次，已达移速上限"
                    })
                    continue

            result = self._settle_action(agent, action)
            result["action_index"] = action_index
            all_results[agent_id].append(result)

            if atype in ("move", "move_to") and result.get("success"):
                moved_counts[agent_id] = moved_counts.get(agent_id, 0) + 1

        return dict(all_results)

    def _settle_action(self, agent: AgentState, action: dict) -> dict:
        """Settle a single action. Returns result dict."""
        atype = action.get("type", "")
        method = getattr(self, f"_do_{atype}", None)
        if method is None:
            return {"type": atype, "success": False, "error_code": "INVALID_ACTION_TYPE",
                    "detail": f"未知行动类型: {atype}"}
        try:
            return method(agent, action)
        except Exception as e:
            return {"type": atype, "success": False, "error_code": "INTERNAL_ERROR", "detail": str(e)}

    # ── Action Handlers ───────────────────────────
    def _do_move(self, agent: AgentState, action: dict) -> dict:
        direction = action.get("direction", "")
        dirs = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
                "n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
        dx, dy = dirs.get(direction, (0, 0))
        if dx == 0 and dy == 0:
            return {"type": "move", "success": False, "error_code": "INVALID_TARGET", "detail": "无效方向"}

        # Cancel pod deploy/dismantle on move
        if agent.status in (ActionStatus.DISMANTLING, ActionStatus.DEPLOYING):
            self._cancel_pod_action(agent)

        nx, ny = agent.position.x + dx, agent.position.y + dy
        if not self.in_bounds(nx, ny):
            return {"type": "move", "success": False, "error_code": "OUT_OF_RANGE", "detail": "目标超出地图边界"}
        tile = self.get_tile(nx, ny)
        if not tile or not tile.passable:
            if tile:
                if tile.l1 in IMPASSABLE:
                    reason = f"地形不可通行({tile.l1.value})"
                elif tile.l2_type == 'stone' and tile.stone_amount > 0:
                    reason = f"被石料阻挡(需先开采, 目标{tile.l1.value})"
                elif tile.structure:
                    if tile.structure.building_type == BuildingType.WALL:
                        reason = "被墙壁阻挡"
                    elif tile.structure.building_type == BuildingType.DOOR and not tile.structure.open:
                        reason = "被关闭的门阻挡"
                    else:
                        reason = f"被建筑阻挡({tile.structure.building_type.value})"
                else:
                    reason = f"目标不可通行({tile.l1.value})"
            else:
                reason = "目标格不存在"
            return {"type": "move", "success": False, "error_code": "BLOCKED", "detail": reason}
        if agent.energy < ENERGY_MOVE:
            return {"type": "move", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        # D-2: Shield blocks other agents from entering
        shielding_pod = self._get_shielding_pod(nx, ny)
        if shielding_pod and shielding_pod != agent.agent_id:
            return {"type": "move", "success": False, "error_code": "BLOCKED",
                    "detail": "降落仓护盾范围内不可进入"}

        agent.energy -= ENERGY_MOVE
        old_pos = (agent.position.x, agent.position.y)
        agent.position = Position(nx, ny)
        self._log_event("agent_move", {"agent_id": agent.agent_id, "from": list(old_pos), "to": [nx, ny], "energy": agent.energy})
        self._log_change("agent_move", agent_id=agent.agent_id, from_pos=list(old_pos), to_pos=[nx, ny])
        return {"type": "move", "success": True, "detail": f"移动到 ({nx}, {ny})"}

    def _do_move_to(self, agent: AgentState, action: dict) -> dict:
        dest = action.get("destination", {})
        tx, ty = dest.get("x", agent.position.x), dest.get("y", agent.position.y)
        if not self.in_bounds(tx, ty):
            return {"type": "move_to", "success": False, "error_code": "INVALID_TARGET", "detail": "目标超出地图边界"}

        agent.status = ActionStatus.MOVING
        agent.action_target = Position(tx, ty)
        agent.action_remaining = -1  # indefinite
        return {"type": "move_to", "success": True, "detail": f"开始前往 ({tx}, {ty})"}

    def _do_toggle_door(self, agent: AgentState, action: dict) -> dict:
        """Toggle a door open/closed. Free action — no energy cost."""
        target = action.get("target", {})
        tx, ty = target.get("x", -1), target.get("y", -1)
        if not self.in_bounds(tx, ty):
            return {"type": "toggle_door", "success": False, "error_code": "INVALID_TARGET", "detail": "目标坐标无效"}
        if agent.position.dist(Position(tx, ty)) > 0:
            return {"type": "toggle_door", "success": False, "error_code": "OUT_OF_RANGE", "detail": "需站在门所在格"}
        tile = self.get_tile(tx, ty)
        if not tile or not tile.structure or tile.structure.building_type != BuildingType.DOOR:
            return {"type": "toggle_door", "success": False, "error_code": "STRUCTURE_NOT_FOUND", "detail": "该格无门"}

        tile.structure.open = not tile.structure.open
        state = "开启" if tile.structure.open else "关闭"
        return {"type": "toggle_door", "success": True, "detail": f"门已{state}"}

    def _do_mine(self, agent: AgentState, action: dict) -> dict:
        target = action.get("target", {})
        tx, ty = target.get("x", -1), target.get("y", -1)
        if not self.in_bounds(tx, ty):
            return {"type": "mine", "success": False, "error_code": "INVALID_TARGET", "detail": "目标坐标无效"}
        if agent.position.dist(Position(tx, ty)) > 1:
            return {"type": "mine", "success": False, "error_code": "OUT_OF_RANGE", "detail": f"目标不在相邻格 (当前:{agent.position.x},{agent.position.y} → 目标:{tx},{ty} 距离:{agent.position.dist(Position(tx, ty))})"}
        if agent.energy < ENERGY_MINE:
            return {"type": "mine", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        tile = self.get_tile(tx, ty)
        if not tile:
            return {"type": "mine", "success": False, "error_code": "INVALID_TARGET", "detail": "目标格不存在"}

        # Check if tile has minable Stone
        if tile.l2_type != 'stone' or tile.stone_amount <= 0:
            return {"type": "mine", "success": False, "error_code": "INVALID_TARGET", "detail": "该格无可开采资源"}

        # Agent must stand on non-Stone, non-water/trench ground to mine
        agent_tile = self.get_tile(agent.position.x, agent.position.y)
        if not agent_tile:
            return {"type": "mine", "success": False, "error_code": "INVALID_TARGET", "detail": "无法确定站立位置"}
        if agent_tile.l1 in IMPASSABLE:
            return {"type": "mine", "success": False, "error_code": "INVALID_TARGET", "detail": f"站在{tile.l1.value}上不可采掘"}
        if agent_tile.l2_type == 'stone' and agent_tile.stone_amount > 0:
            return {"type": "mine", "success": False, "error_code": "INVALID_TARGET", "detail": "站在石料矿层上无法开采——需站在平地/沙地/基岩上开采相邻石料"}

        # Tool check
        held_tool = self.get_held_tool(agent)
        tool_info = TOOLS.get(held_tool, {}) if held_tool else None
        max_hardness = tool_info["max_hardness"] if tool_info else TOOL_HARDNESS.get(None, 3)
        bonus = tool_info["bonus"] if tool_info else TOOL_BONUS.get(None, 0.0)

        # Check if ore present and requires hardness
        if tile.ore_type:
            ore_hardness = RESOURCE_HARDNESS.get(self._ore_to_item_id(tile.ore_type), 5)
            if max_hardness < ore_hardness:
                ore_name = self._ore_name(tile.ore_type)
                return {"type": "mine", "success": False, "error_code": "TOOL_REQUIRED",
                        "detail": f"采集{ore_name}矿需要更好的工具 (硬度{ore_hardness} > 工具{max_hardness})"}

        agent.energy -= ENERGY_MINE
        agent.last_action_tick = self.tick_number

        # Harvest efficiency formula: output = base_output × (1 + tool_bonus) × con_modifier
        con_modifier = {1: 1.0, 2: 1.2, 3: 1.5}.get(agent.constitution, 1.0)

        # Mine Stone
        tile.stone_amount -= 1
        amount = max(1, int(1 * (1 + bonus) * con_modifier))
        self.add_item(agent, "stone", amount)

        result_detail = f"采集石料×{amount}"
        ore_result = None

        # Mine ore if present
        if tile.ore_type and tile.ore_amount > 0:
            tile.ore_amount -= 1
            ore_amount = max(1, int(1 * (1 + bonus) * con_modifier))
            ore_item_id = self._ore_to_item_id(tile.ore_type)
            self.add_item(agent, ore_item_id, ore_amount)
            ore_result = ore_item_id
            result_detail += f", {self._ore_name(tile.ore_type)}矿×{ore_amount}"

        # Stone depleted?
        if tile.stone_amount <= 0:
            tile.l2_type = ''
            # Rubble chance
            if random.random() < 0.20:
                tile.veg_type = 'rubble'
                tile.veg_yield = 1
            result_detail += ", 石料矿层采尽"
            self._log_change("resource_deplete", tile=(tx, ty))

        # Ore depleted?
        if tile.ore_amount <= 0:
            tile.ore_type = ''

        # Tool durability
        if held_tool:
            self._reduce_durability(agent, held_tool)

        self._log_event("agent_mine", {"agent_id": agent.agent_id, "position": [tx, ty],
                        "stone_remaining": tile.stone_amount, "ore": ore_result})

        return {"type": "mine", "success": True, "detail": result_detail,
                "ore_found": ore_result, "stone_remaining": tile.stone_amount}

    def _do_chop(self, agent: AgentState, action: dict) -> dict:
        target = action.get("target", {})
        tx, ty = target.get("x", -1), target.get("y", -1)
        if not self.in_bounds(tx, ty):
            return {"type": "chop", "success": False, "error_code": "INVALID_TARGET", "detail": "目标坐标无效"}
        if agent.position.dist(Position(tx, ty)) > 1:
            return {"type": "chop", "success": False, "error_code": "OUT_OF_RANGE", "detail": f"目标不在相邻格 (当前:{agent.position.x},{agent.position.y} → 目标:{tx},{ty} 距离:{agent.position.dist(Position(tx, ty))})"}
        if agent.energy < ENERGY_CHOP:
            return {"type": "chop", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        tile = self.get_tile(tx, ty)
        if not tile:
            return {"type": "chop", "success": False, "error_code": "INVALID_TARGET", "detail": "目标格不存在"}

        veg = tile.veg_type
        if veg in ("ashbush", "greytree", "wallmoss"):
            wood_yield = tile.veg_yield
            # Harvest efficiency formula: output = base_yield × (1 + tool_bonus) × con_modifier
            held_tool = self.get_held_tool(agent)
            tool_info = TOOLS.get(held_tool, {}) if held_tool else None
            chop_bonus = tool_info["bonus"] if tool_info else TOOL_BONUS.get(None, 0.0)
            con_modifier = {1: 1.0, 2: 1.2, 3: 1.5}.get(agent.constitution, 1.0)
            wood_yield = max(1, int(wood_yield * (1 + chop_bonus) * con_modifier))

            # Track for regrowth (P2): wood-yielding vegetation
            from .config import WOOD_VEG_TYPES
            if veg in WOOD_VEG_TYPES:
                self._harvested_wood[(tx, ty)] = veg
                tile.regrow_timer = 0

            tile.veg_type = ''
            tile.veg_yield = 0
            agent.energy -= ENERGY_CHOP
            self.add_item(agent, "wood", wood_yield)

            # Small organic_fuel drop chance per vegetation type
            fuel_chance = {"ashbush": 0.25, "wallmoss": 0.15, "greytree": 0.05}.get(veg, 0)
            if fuel_chance > 0 and random.random() < fuel_chance:
                self.add_item(agent, "organic_fuel", 1)
                fuel_msg = "，获得有机燃料×1"
            else:
                fuel_msg = ""

            self._log_event("agent_chop", {"agent_id": agent.agent_id, "position": [tx, ty], "resource": veg, "yield": wood_yield})

            if held_tool:
                self._reduce_durability(agent, held_tool)
            return {"type": "chop", "success": True, "detail": f"采集木质×{wood_yield}{fuel_msg}"}
        elif veg == 'rubble':
            wood_yield = 1
            # Apply efficiency formula to rubble clearing too
            held_tool = self.get_held_tool(agent)
            tool_info = TOOLS.get(held_tool, {}) if held_tool else None
            chop_bonus = tool_info["bonus"] if tool_info else TOOL_BONUS.get(None, 0.0)
            con_modifier = {1: 1.0, 2: 1.2, 3: 1.5}.get(agent.constitution, 1.0)
            stone_yield = max(1, int(wood_yield * (1 + chop_bonus) * con_modifier))
            tile.veg_type = ''
            tile.veg_yield = 0
            agent.energy -= ENERGY_CHOP
            self.add_item(agent, "stone", stone_yield)
            self._log_event("agent_chop", {"agent_id": agent.agent_id, "position": [tx, ty], "resource": "rubble", "yield": stone_yield})

            if held_tool:
                self._reduce_durability(agent, held_tool)
            return {"type": "chop", "success": True, "detail": f"清理碎石，获得石料×{stone_yield}"}

        return {"type": "chop", "success": False, "error_code": "INVALID_TARGET", "detail": "该格无可采集植被"}

    def _do_pickup(self, agent: AgentState, action: dict) -> dict:
        x, y = agent.position.x, agent.position.y
        key = (x, y)
        if key not in self.ground_items or not self.ground_items[key].items:
            return {"type": "pickup", "success": False, "error_code": "INVALID_TARGET", "detail": "该格无可拾取物品"}
        if agent.energy < ENERGY_PICKUP:
            return {"type": "pickup", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        ground = self.ground_items[key]
        picked = []
        for item_id, amount in ground.items:
            self.add_item(agent, item_id, amount)
            picked.append(f"{item_id}×{amount}")
        del self.ground_items[key]
        agent.energy -= ENERGY_PICKUP
        return {"type": "pickup", "success": True, "detail": f"拾取: {', '.join(picked)}"}

    def _do_drop(self, agent: AgentState, action: dict) -> dict:
        item_id = action.get("item_id", "")
        amount = action.get("amount", 1)
        if not self.has_item(agent, item_id, amount):
            return {"type": "drop", "success": False, "error_code": "INVENTORY_FULL", "detail": "背包中无此物品或数量不足"}
        self.remove_item(agent, item_id, amount)
        self._add_ground_item(agent.position.x, agent.position.y, item_id, amount)
        return {"type": "drop", "success": True, "detail": f"丢弃 {item_id}×{amount}"}

    def _do_rest(self, agent: AgentState, action: dict) -> dict:
        agent.energy = min(agent.max_energy, agent.energy + ENERGY_RECOVER_REST)
        self._log_event("agent_rest", {"agent_id": agent.agent_id, "energy": agent.energy})
        return {"type": "rest", "success": True, "detail": f"休息，恢复+{ENERGY_RECOVER_REST}能量"}

    def _do_scan(self, agent: AgentState, action: dict) -> dict:
        if agent.energy < ENERGY_SCAN:
            return {"type": "scan", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}
        agent.energy -= ENERGY_SCAN
        # Reveal hidden ores AND surface stone in 5x5 area
        px, py = agent.position.x, agent.position.y
        found = []
        stone_found = []
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                x, y = px + dx, py + dy
                if not self.in_bounds(x, y): continue
                tile = self.get_tile(x, y)
                if not tile: continue
                # Reveal hidden ores
                if tile.l2_type == 'stone' and tile.ore_type:
                    if not tile.ore_exposed:
                        tile.ore_exposed = True
                    found.append({"x": x, "y": y, "ore": tile.ore_type, "exposed": tile.ore_exposed})
                # Surface stone deposits
                if tile.l2_type == 'stone' and tile.stone_amount > 0:
                    stone_found.append({"x": x, "y": y, "amount": tile.stone_amount})

        self._log_event("agent_scan", {"agent_id": agent.agent_id, "found": len(found), "stone": len(stone_found)})
        exposed = sum(1 for f in found if f.get("exposed"))
        hidden = len(found) - exposed
        detail = f"探测完成: {hidden} 处新矿脉, {exposed} 处已知矿脉, {len(stone_found)} 处石料"
        return {"type": "scan", "success": True, "detail": detail, "found": found, "stone_deposits": stone_found}

    def _do_talk(self, agent: AgentState, action: dict) -> dict:
        target_id = action.get("target_agent", "")
        content = action.get("content", "")
        target = self.agents.get(target_id)
        if not target:
            return {"type": "talk", "success": False, "error_code": "AGENT_NOT_FOUND", "detail": "目标智能体不存在"}
        if agent.position.dist(target.position) > 0:
            return {"type": "talk", "success": False, "error_code": "OUT_OF_RANGE", "detail": "目标不在同一格"}
        self.talk_messages.append({"from": agent.agent_id, "from_name": agent.agent_name,
                                    "to": target_id, "content": content})
        return {"type": "talk", "success": True, "detail": f"消息已发送给 {target.agent_name}"}

    def _do_radio_broadcast(self, agent: AgentState, action: dict) -> dict:
        content = action.get("content", "")
        if agent.energy < ENERGY_RADIO:
            return {"type": "radio_broadcast", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}
        agent.energy -= ENERGY_RADIO
        radio_range = RADIO_RANGE_AMPLIFIED if (agent.equipment.off_hand == "signal_amplifier") else RADIO_RANGE
        self.broadcasts.append({"from": agent.agent_id, "from_name": agent.agent_name,
                                "content": content, "range": radio_range})
        return {"type": "radio_broadcast", "success": True, "detail": f"广播已发送 (范围{radio_range}格)"}

    def _do_radio_direct(self, agent: AgentState, action: dict) -> dict:
        target_id = action.get("target_agent", "")
        content = action.get("content", "")
        target = self.agents.get(target_id)
        if not target:
            return {"type": "radio_direct", "success": False, "error_code": "AGENT_NOT_FOUND", "detail": "目标不存在"}
        radio_range = RADIO_RANGE_AMPLIFIED if (agent.equipment.off_hand == "signal_amplifier") else RADIO_RANGE
        if agent.position.dist(target.position) > radio_range:
            return {"type": "radio_direct", "success": False, "error_code": "OUT_OF_RANGE", "detail": "目标超出通讯范围"}
        if agent.energy < ENERGY_RADIO:
            return {"type": "radio_direct", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}
        agent.energy -= ENERGY_RADIO
        self.direct_messages.append({"from": agent.agent_id, "from_name": agent.agent_name,
                                      "to": target_id, "content": content})
        return {"type": "radio_direct", "success": True, "detail": f"私密消息已发送给 {target.agent_name}"}

    def _do_radio_scan(self, agent: AgentState, action: dict) -> dict:
        if agent.energy < ENERGY_RADIO:
            return {"type": "radio_scan", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}
        agent.energy -= ENERGY_RADIO
        radio_range = RADIO_RANGE_AMPLIFIED if (agent.equipment.off_hand == "signal_amplifier") else RADIO_RANGE
        nearby = []
        for aid, other in self.agents.items():
            if aid != agent.agent_id and other.online:
                d = agent.position.dist(other.position)
                if d <= radio_range:
                    nearby.append({"agent_id": aid, "name": other.agent_name, "distance": d})
        if nearby:
            return {"type": "radio_scan", "success": True, "detail": f"无线电范围内发现 {len(nearby)} 个信号", "agents": nearby}
        else:
            return {"type": "radio_scan", "success": True, "detail": f"无线电范围({radio_range}格)内未探测到其他信号", "agents": []}

    def _do_attack(self, agent: AgentState, action: dict) -> dict:
        # Check for creature target
        target_creature_id = action.get("target_creature")
        if target_creature_id:
            return self._do_attack_creature(agent, action, target_creature_id)

        target_id = action.get("target_agent", "")
        target = self.agents.get(target_id)
        if not target:
            return {"type": "attack", "success": False, "error_code": "AGENT_NOT_FOUND", "detail": "目标不存在"}

        # D-3/D-4: Shield boundary checks — block PvP attacks across shield lines
        for aid, other in self.agents.items():
            if not other.drop_pod_pos or not other.drop_pod_deployed:
                continue
            pod_pos = other.drop_pod_pos
            attacker_in = agent.position.dist(pod_pos) <= DROP_POD_SHIELD_RANGE
            target_in = target.position.dist(pod_pos) <= DROP_POD_SHIELD_RANGE
            if attacker_in and not target_in:
                # D-3: Attacker inside shield, target outside — block
                return {"type": "attack", "success": False, "error_code": "SHIELD_BLOCK",
                        "detail": "护盾范围内不可向外攻击"}
            if not attacker_in and target_in:
                # D-4: Target inside shield, attacker outside — block
                return {"type": "attack", "success": False, "error_code": "SHIELD_BLOCK",
                        "detail": "目标在降落仓护盾保护内"}

        weapon = self.get_held_weapon(agent)
        if weapon:
            weapon_type = weapon["type"]
            damage = weapon["damage"]
            wp_range = weapon["range"]
            energy_cost = ENERGY_ATTACK_MELEE if weapon_type == "melee" else weapon.get("energy", 3)
        else:
            weapon_type = "melee"
            damage = UNARMED_DAMAGE
            wp_range = 1
            energy_cost = ENERGY_ATTACK_MELEE

        d = agent.position.dist(target.position)
        if d > wp_range:
            return {"type": "attack", "success": False, "error_code": "OUT_OF_RANGE", "detail": f"目标距离{d}格超出武器射程{wp_range}"}
        if agent.energy < energy_cost:
            return {"type": "attack", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        agent.energy -= energy_cost

        # Hit calculation
        if weapon_type == "melee":
            target_moving = target.status == ActionStatus.MOVING
            hit_rate = MELEE_HIT_STATIC if not target_moving else MELEE_HIT_MOVING
            dmg_mod = 1.0
        else:
            ranges = weapon.get("ranges", [2, 4, 6])
            if d <= ranges[0]:
                zone = "optimal"
            elif d <= ranges[1]:
                zone = "effective"
            else:
                zone = "limit"
            hit_rate = RANGED_HIT[zone]
            dmg_mod = RANGED_DMG_MOD[zone]
            target_moving = target.status == ActionStatus.MOVING
            if target_moving:
                hit_rate *= REMOTE_MOVING_MOD

        if random.random() > hit_rate:
            return {"type": "attack", "success": True, "hit": False, "detail": "未命中", "hit_rate": hit_rate}

        # Damage calculation
        agi_mod = 1 + (agent.agility - target.agility) * 0.05
        agi_mod = max(0.75, min(1.25, agi_mod))
        env_mod = 0.8 if self.day_phase == DayPhase.NIGHT and weapon_type == "ranged" else 1.0
        final_dmg = max(1, int(damage * dmg_mod * agi_mod * env_mod))

        # Armor reduction
        armor_id = target.equipment.armor
        armor_def = ARMORS.get(armor_id, {}).get("defense", 0) if armor_id else 0
        final_dmg = max(1, final_dmg - armor_def)

        target.health -= final_dmg

        # B-1: Notify target of attack
        self.tick_notifications[target_id].append({
            "type": "attacked", "attacker_id": agent.agent_id,
            "attacker_name": agent.agent_name, "damage": final_dmg,
            "hp_remaining": max(0, target.health),
        })
        # R-1: Interrupt target's crafting and pod actions
        self._interrupt_crafting(target)
        self._cancel_pod_action(target)

        if weapon and weapon.get("id"):
            self._reduce_durability(agent, weapon["id"])
        # Armor durability
        if armor_id:
            self._reduce_durability(target, armor_id)

        result = {"type": "attack", "success": True, "hit": True, "damage_dealt": final_dmg,
                  "target_hp": max(0, target.health), "detail": f"造成 {final_dmg} 点伤害"}

        if target.health <= 0:
            result["target_killed"] = True
            self._handle_death(target)

        return result

    def _do_attack_creature(self, agent: AgentState, action: dict, creature_id: str) -> dict:
        """Attack a creature target."""
        creature = self.creatures.get(creature_id)
        if not creature:
            return {"type": "attack", "success": False, "error_code": "TARGET_NOT_FOUND", "detail": "目标生物不存在"}

        weapon = self.get_held_weapon(agent)
        if weapon:
            damage = weapon["damage"]
            wp_range = weapon["range"]
            energy_cost = ENERGY_ATTACK_MELEE if weapon["type"] == "melee" else weapon.get("energy", 3)
        else:
            damage = UNARMED_DAMAGE
            wp_range = 1
            energy_cost = ENERGY_ATTACK_MELEE

        d = agent.position.dist(creature.position)
        if d > wp_range:
            return {"type": "attack", "success": False, "error_code": "OUT_OF_RANGE",
                    "detail": f"生物距离{d}格超出武器射程{wp_range}"}
        if agent.energy < energy_cost:
            return {"type": "attack", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        agent.energy -= energy_cost

        # Creatures don't dodge — always hit
        agi_mod = 1.0 + agent.agility * 0.05
        final_dmg = max(1, int(damage * agi_mod))

        creature.hp -= final_dmg
        # Add attacker to aggro list
        if agent.agent_id not in creature.aggro_list:
            creature.aggro_list.append(agent.agent_id)
        creature.last_attacked_tick = self.tick_number

        if weapon and weapon.get("id"):
            self._reduce_durability(agent, weapon["id"])

        result = {"type": "attack", "success": True, "hit": True, "damage_dealt": final_dmg,
                  "target_type": "creature", "target_creature_type": creature.creature_type,
                  "target_hp": max(0, creature.hp),
                  "detail": f"攻击 {creature.creature_type} 造成 {final_dmg} 点伤害"}

        if creature.hp <= 0:
            self._handle_creature_death(agent, creature)
            result["target_killed"] = True
            result["drops"] = result.get("drops", [])

        return result

    def _handle_creature_death(self, killer: AgentState, creature: Creature):
        """Handle creature death — drops and cleanup."""
        drops = CREATURE_DROPS.get(creature.creature_type, {})
        # Primary drop (always)
        primary = drops.get("primary")
        if primary:
            item_id, min_amt, max_amt, _ = primary
            amount = random.randint(min_amt, max_amt)
            self._add_ground_item(creature.position.x, creature.position.y, item_id, amount)
        # Secondary drop (probability)
        secondary = drops.get("secondary")
        if secondary:
            item_id, min_amt, max_amt, prob = secondary
            if random.random() < prob:
                amount = random.randint(min_amt, max_amt)
                self._add_ground_item(creature.position.x, creature.position.y, item_id, amount)

        killer.creature_kills += 1
        self._log_event("creature_killed", {
            "creature_id": creature.creature_id, "creature_type": creature.creature_type,
            "killer": killer.agent_id,
        })
        del self.creatures[creature.creature_id]

    def _do_equip(self, agent: AgentState, action: dict) -> dict:
        item_id = action.get("item_id", "")
        if not self.has_item(agent, item_id, 1):
            return {"type": "equip", "success": False, "error_code": "INVENTORY_FULL", "detail": "背包中无此物品"}
        slot = action.get("slot", "main_hand")
        if slot not in ("main_hand", "off_hand", "armor"):
            return {"type": "equip", "success": False, "error_code": "INVALID_TARGET", "detail": "无效装备槽"}

        # Return currently equipped item to inventory (with durability)
        current = getattr(agent.equipment, slot)
        if current:
            dur = getattr(agent.equipment, f"{slot}_durability")
            self.add_item(agent, current, 1)
            # Set durability on the returned item
            if dur is not None:
                for inv in agent.inventory:
                    if inv.item_id == current and inv.durability is None:
                        inv.durability = dur
                        break
            setattr(agent.equipment, f"{slot}_durability", None)

        # Equip new item
        self.remove_item(agent, item_id, 1)
        setattr(agent.equipment, slot, item_id)

        # Set durability on equipment slot
        max_dur = None
        if item_id in TOOLS: max_dur = TOOLS[item_id]["durability"]
        elif item_id in WEAPONS: max_dur = WEAPONS[item_id]["durability"]
        elif item_id in ARMORS: max_dur = ARMORS[item_id]["durability"]
        elif item_id in ACCESSORIES: max_dur = ACCESSORIES[item_id]["durability"]
        setattr(agent.equipment, f"{slot}_durability", max_dur)

        return {"type": "equip", "success": True, "detail": f"已装备 {item_id}"}

    def _do_unequip(self, agent: AgentState, action: dict) -> dict:
        slot = action.get("slot", "main_hand")
        if slot not in ("main_hand", "off_hand", "armor"):
            return {"type": "unequip", "success": False, "error_code": "INVALID_TARGET", "detail": "无效装备槽"}
        current = getattr(agent.equipment, slot)
        if not current:
            return {"type": "unequip", "success": False, "error_code": "INVALID_TARGET", "detail": "该槽位无装备"}
        dur = getattr(agent.equipment, f"{slot}_durability")
        self.add_item(agent, current, 1)
        # Set durability on the returned item
        if dur is not None:
            for inv in agent.inventory:
                if inv.item_id == current and inv.durability is None:
                    inv.durability = dur
                    break
        setattr(agent.equipment, slot, None)
        setattr(agent.equipment, f"{slot}_durability", None)
        return {"type": "unequip", "success": True, "detail": f"已卸下 {current}"}

    def _do_use(self, agent: AgentState, action: dict) -> dict:
        item_id = action.get("item_id", "")
        if item_id == "repair_kit":
            if not self.has_item(agent, "repair_kit"): return {"type": "use", "success": False, "error_code": "INVENTORY_FULL", "detail": "无修理包"}
            self.remove_item(agent, "repair_kit", 1)
            agent.health = min(agent.max_health, agent.health + HP_REPAIR_KIT)
            return {"type": "use", "success": True, "detail": f"使用修理包，恢复+{HP_REPAIR_KIT}HP"}
        elif item_id == "battery":
            if not self.has_item(agent, "battery"): return {"type": "use", "success": False, "error_code": "INVENTORY_FULL", "detail": "无电池"}
            self.remove_item(agent, "battery", 1)
            agent.energy = min(agent.max_energy, agent.energy + ENERGY_BATTERY)
            return {"type": "use", "success": True, "detail": f"使用电池，恢复+{ENERGY_BATTERY}能量"}
        elif item_id == "radiation_antidote":
            if not self.has_item(agent, "radiation_antidote"): return {"type": "use", "success": False, "error_code": "INVENTORY_FULL", "detail": "无辐射药剂"}
            self.remove_item(agent, "radiation_antidote", 1)
            agent.radiation_debuff = False
            return {"type": "use", "success": True, "detail": "辐射效果已消除"}
        return {"type": "use", "success": False, "error_code": "INVALID_TARGET", "detail": f"不可使用的物品: {item_id}"}

    def _do_fuel_power_node(self, agent: AgentState, action: dict) -> dict:
        """Fuel a power node with organic materials or uranium ore."""
        # Find power node at agent's position
        tile = self.get_tile(agent.position.x, agent.position.y)
        if not tile or not tile.structure or tile.structure.building_type != BuildingType.POWER_NODE:
            return {"type": "fuel_power_node", "success": False, "error_code": "STRUCTURE_NOT_FOUND",
                    "detail": "需站在能源节点所在格"}

        pn_id = f"pn-{tile.structure.structure_id}"
        pn = self.power_nodes.get(pn_id)
        if not pn:
            return {"type": "fuel_power_node", "success": False, "error_code": "STRUCTURE_NOT_FOUND",
                    "detail": "能源节点数据异常"}

        if agent.energy < 1:
            return {"type": "fuel_power_node", "success": False, "error_code": "INSUFFICIENT_ENERGY",
                    "detail": "能量不足(需1点能量操作)"}

        item_id = action.get("item_id", "")
        amount = action.get("amount", 1)
        if amount < 1:
            return {"type": "fuel_power_node", "success": False, "error_code": "INVALID_TARGET",
                    "detail": "燃料数量无效"}

        # Fuel value map
        fuel_values = {"wood": 10, "organic_fiber": 10, "organic_fuel": 10, "uranium_ore": 50}
        if item_id not in fuel_values:
            return {"type": "fuel_power_node", "success": False, "error_code": "INVALID_TARGET",
                    "detail": f"不可作为燃料: {item_id}(可用: wood/organic_fiber/organic_fuel/uranium_ore)"}

        fuel_value = fuel_values[item_id]

        # Check if agent has the item
        if not self.has_item(agent, item_id, amount):
            return {"type": "fuel_power_node", "success": False, "error_code": "MISSING_MATERIALS",
                    "detail": f"缺少 {item_id}×{amount}"}

        # Calculate available space in power node
        available_space = max(POWER_NODE_MAX_ENERGY, pn.capacity) - pn.stored
        if available_space <= 0:
            return {"type": "fuel_power_node", "success": False, "error_code": "FULL",
                    "detail": "能源节点已满"}

        # Limit to available space
        max_by_space = available_space // fuel_value
        actual_amount = min(amount, max_by_space)
        if actual_amount < 1:
            return {"type": "fuel_power_node", "success": False, "error_code": "FULL",
                    "detail": f"能源节点剩余空间不足(剩余{available_space}, 每{item_id}提供{fuel_value})"}

        energy_gain = fuel_value * actual_amount

        # Consume items
        self.remove_item(agent, item_id, actual_amount)

        # Add energy to power node
        max_cap = max(POWER_NODE_MAX_ENERGY, pn.capacity)
        pn.stored = min(max_cap, pn.stored + energy_gain)

        # Agent energy cost (operation cost)
        agent.energy -= 1

        return {"type": "fuel_power_node", "success": True,
                "detail": f"投入 {item_id}×{actual_amount}，获得{energy_gain}点能量，当前储量{pn.stored}/{max_cap}"}

    def _do_craft(self, agent: AgentState, action: dict) -> dict:
        recipe_id = action.get("recipe", "")
        # Find recipe
        recipe = FURNACE_RECIPES.get(recipe_id) or HANDCRAFT_RECIPES.get(recipe_id) or WORKBENCH_RECIPES.get(recipe_id)
        if not recipe:
            return {"type": "craft", "success": False, "error_code": "RECIPE_UNKNOWN", "detail": f"未知配方: {recipe_id}"}

        # Check materials
        if not self.has_item(agent, list(recipe["materials"].items())[0][0], list(recipe["materials"].values())[0]):
            # Check all materials
            for mat, amt in recipe["materials"].items():
                if not self.has_item(agent, mat, amt):
                    missing_map = {mat: amt}
                    return {"type": "craft", "success": False, "error_code": "MISSING_MATERIALS",
                            "detail": f"缺少 {mat}×{amt}", "missing": missing_map}

        if agent.energy < ENERGY_CRAFT:
            return {"type": "craft", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        # Power check for furnace/workbench
        if recipe_id in FURNACE_RECIPES or recipe_id in WORKBENCH_RECIPES:
            # Check if near furnace/workbench
            near_station = False
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if dy == 0 and dx == 0: continue
                    nx, ny = agent.position.x + dx, agent.position.y + dy
                    tile = self.get_tile(nx, ny)
                    if tile and tile.structure:
                        if recipe_id in FURNACE_RECIPES and tile.structure.building_type == BuildingType.FURNACE:
                            near_station = True
                        if recipe_id in WORKBENCH_RECIPES and tile.structure.building_type == BuildingType.WORKBENCH:
                            near_station = True
            if not near_station:
                station = "熔炉" if recipe_id in FURNACE_RECIPES else "工作台"
                return {"type": "craft", "success": False, "error_code": "TOOL_REQUIRED",
                        "detail": f"需要在{station}旁合成"}

            if not self.has_craft_power(agent):
                return {"type": "craft", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "电力不足"}

            # Consume power immediately at start of crafting
            power_cost = recipe.get("power", 0)
            if power_cost > 0:
                if not self.consume_power(agent, power_cost):
                    return {"type": "craft", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "电力不足"}

        # Multi-tick crafting
        craft_ticks = recipe.get("ticks", 0)
        if craft_ticks > 0:
            agent.status = ActionStatus.CRAFTING
            agent.action_remaining = craft_ticks
            agent.action_data = {"recipe": recipe_id, "recipe_def": recipe}
        else:
            self._complete_craft(agent, recipe_id, recipe)

        return {"type": "craft", "success": True, "detail": f"开始合成: {recipe_id}", "ticks": craft_ticks}

    def _complete_craft(self, agent: AgentState, recipe_id: str, recipe: dict):
        """Complete a crafting action."""
        # Consume materials
        for mat, amt in recipe["materials"].items():
            self.remove_item(agent, mat, amt)
        # Produce output
        output_id = recipe.get("output", recipe_id)
        output_amount = recipe.get("amount", 1)
        self.add_item(agent, output_id, output_amount)
        agent.status = ActionStatus.IDLE
        agent.action_data = {}
        agent.action_remaining = 0
        self._log_change("craft_complete", agent_id=agent.agent_id, recipe=recipe_id, output=output_id)

    def _do_build(self, agent: AgentState, action: dict) -> dict:
        building_type = action.get("building_type", "")
        target = action.get("target", {})
        tx, ty = target.get("x", agent.position.x), target.get("y", agent.position.y)
        if not self.in_bounds(tx, ty):
            return {"type": "build", "success": False, "error_code": "INVALID_TARGET", "detail": "目标超出地图边界"}
        if agent.position.dist(Position(tx, ty)) > 1:
            return {"type": "build", "success": False, "error_code": "OUT_OF_RANGE", "detail": f"目标不在建造范围 (当前:{agent.position.x},{agent.position.y} → 目标:{tx},{ty} 距离:{agent.position.dist(Position(tx, ty))}, 最大范围:1格)"}
        # Workbench/furnace/power_node must be built on current tile (dist=0)
        if building_type in ("workbench", "furnace", "power_node") and agent.position.dist(Position(tx, ty)) > 0:
            return {"type": "build", "success": False, "error_code": "OUT_OF_RANGE",
                    "detail": "工作台/熔炉/能源节点需建在当前格"}
        if agent.energy < ENERGY_BUILD:
            return {"type": "build", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        tile = self.get_tile(tx, ty)
        if not tile:
            return {"type": "build", "success": False, "error_code": "INVALID_TARGET", "detail": "目标格不存在"}

        # Building rules
        if tile.l1 in IMPASSABLE:
            return {"type": "build", "success": False, "error_code": "TILE_BLOCKED", "detail": f"不可在{tile.l1.value}上建造"}
        if tile.l2_type == 'stone' and tile.stone_amount > 0:
            if building_type in ("wall", "door"):
                pass  # walls/doors can build next to stone
            else:
                return {"type": "build", "success": False, "error_code": "TILE_BLOCKED", "detail": "需先开采石料"}
        if tile.structure:
            return {"type": "build", "success": False, "error_code": "TILE_BLOCKED", "detail": "该格已有建筑"}

        # Check if in another agent's drop pod shield (owner may build within own shield per §7.6.2)
        for aid, other in self.agents.items():
            if other.drop_pod_pos and other.drop_pod_deployed:
                if aid != agent.agent_id and Position(tx, ty).dist(other.drop_pod_pos) <= DROP_POD_SHIELD_RANGE:
                    return {"type": "build", "success": False, "error_code": "TILE_BLOCKED",
                            "detail": "其他幸存者降落仓护盾范围内不可建造"}

        # Check if agent has the building as an inventory item (deploy mode — no material cost)
        deploy_from_inventory = self.has_item(agent, building_type, 1)
        if not deploy_from_inventory:
            # Fallback: require BUILD_COSTS materials
            costs = BUILD_COSTS.get(building_type, {})
            for mat, amt in costs.items():
                if not self.has_item(agent, mat, amt):
                    costs_str = ", ".join(f"{m}×{a}" for m, a in BUILD_COSTS.get(building_type, {}).items())
                    return {"type": "build", "success": False, "error_code": "MISSING_MATERIALS",
                            "detail": f"缺少 {mat}×{amt} (合成{building_type}需: {costs_str})", "missing": {mat: amt}}

            # Consume materials
            for mat, amt in costs.items():
                self.remove_item(agent, mat, amt)
        else:
            # Deploy from inventory — consume the item
            self.remove_item(agent, building_type, 1)

        agent.energy -= ENERGY_BUILD

        structure = self.add_structure(building_type, Position(tx, ty), agent.agent_id)
        return {"type": "build", "success": True, "detail": f"建造 {building_type} 完成", "structure_id": structure.structure_id}

    def _do_dismantle(self, agent: AgentState, action: dict) -> dict:
        target = action.get("target", {})
        tx, ty = target.get("x", -1), target.get("y", -1)
        tile = self.get_tile(tx, ty) if self.in_bounds(tx, ty) else None
        if not tile or not tile.structure:
            return {"type": "dismantle", "success": False, "error_code": "STRUCTURE_NOT_FOUND", "detail": "该格无建筑"}
        if agent.energy < ENERGY_DISMANTLE:
            return {"type": "dismantle", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}

        btype = tile.structure.building_type
        dist = agent.position.dist(Position(tx, ty))

        # Walls/doors can be dismantled from adjacent tile; other buildings require standing on them
        if btype in (BuildingType.WALL, BuildingType.DOOR):
            if dist > 1:
                return {"type": "dismantle", "success": False, "error_code": "OUT_OF_RANGE",
                        "detail": f"需站在目标相邻格 (当前距离:{dist})"}
            # Only owner can dismantle walls/doors
            if tile.structure.owner_id != agent.agent_id:
                return {"type": "dismantle", "success": False, "error_code": "NOT_OWNER",
                        "detail": "只能拆除自己的建筑"}
        else:
            if dist > 0:
                return {"type": "dismantle", "success": False, "error_code": "OUT_OF_RANGE",
                        "detail": "需站在建筑所在格"}

        sid = tile.structure.structure_id
        self._destroy_structure(sid)
        agent.energy -= ENERGY_DISMANTLE
        return {"type": "dismantle", "success": True, "detail": "拆除完成"}

    def _do_dismantle_pod(self, agent: AgentState, action: dict) -> dict:
        """Start 4-tick pod dismantle process. Shield drops immediately."""
        if not agent.drop_pod_pos or agent.position.dist(agent.drop_pod_pos) > 0:
            return {"type": "dismantle_pod", "success": False, "error_code": "OUT_OF_RANGE",
                    "detail": "需站在降落仓所在格"}
        if not agent.drop_pod_deployed:
            return {"type": "dismantle_pod", "success": False, "error_code": "INVALID_TARGET",
                    "detail": "降落仓未部署"}
        if agent.status not in (ActionStatus.IDLE,):
            return {"type": "dismantle_pod", "success": False, "error_code": "BUSY",
                    "detail": "当前状态无法拆解降落仓"}
        if agent.energy < ENERGY_DISMANTLE:
            return {"type": "dismantle_pod", "success": False, "error_code": "INSUFFICIENT_ENERGY",
                    "detail": "能量不足"}

        # Check 5 free inventory slots for pod parts
        free_slots = INVENTORY_SLOTS - len(agent.inventory)
        if free_slots < 5:
            return {"type": "dismantle_pod", "success": False, "error_code": "INVENTORY_FULL",
                    "detail": "背包空间不足(需要5个空位放置降落仓组件)"}

        # Shield disappears immediately — generator is packing
        agent.drop_pod_deployed = False

        # Start dismantling process
        agent.status = ActionStatus.DISMANTLING
        agent.action_remaining = DEPLOY_DISMANTLE_TICKS
        agent.action_data = {}
        agent.energy -= ENERGY_DISMANTLE
        return {"type": "dismantle_pod", "success": True, "detail": f"开始拆解降落仓({DEPLOY_DISMANTLE_TICKS}tick)"}

    def _do_deploy_pod(self, agent: AgentState, action: dict) -> dict:
        """Start 4-tick pod deploy process. Requires 5 pod parts in inventory."""
        from .config import POD_PARTS
        # Check all 5 pod parts
        for part in POD_PARTS:
            if not self.has_item(agent, part, 1):
                return {"type": "deploy_pod", "success": False, "error_code": "MISSING_MATERIALS",
                        "detail": f"缺少{part}(需要全部5个降落仓组件)"}

        if agent.drop_pod_deployed:
            return {"type": "deploy_pod", "success": False, "error_code": "INVALID_TARGET",
                    "detail": "降落仓已部署"}
        if agent.status not in (ActionStatus.IDLE,):
            return {"type": "deploy_pod", "success": False, "error_code": "BUSY",
                    "detail": "当前状态无法部署降落仓"}
        if agent.energy < ENERGY_DISMANTLE:
            return {"type": "deploy_pod", "success": False, "error_code": "INSUFFICIENT_ENERGY",
                    "detail": "能量不足"}

        # Check destination tile is valid (current tile must be buildable)
        tile = self.get_tile(agent.position.x, agent.position.y)
        if not tile or tile.l1 in IMPASSABLE:
            return {"type": "deploy_pod", "success": False, "error_code": "TILE_BLOCKED",
                    "detail": "当前格不可部署降落仓"}
        if tile.structure:
            return {"type": "deploy_pod", "success": False, "error_code": "TILE_BLOCKED",
                    "detail": "当前格已有建筑"}

        # Start deployment process (parts consumed at completion)
        agent.status = ActionStatus.DEPLOYING
        agent.action_remaining = DEPLOY_DISMANTLE_TICKS
        agent.action_data = {}
        agent.energy -= ENERGY_DISMANTLE
        return {"type": "deploy_pod", "success": True, "detail": f"开始部署降落仓({DEPLOY_DISMANTLE_TICKS}tick)"}

    def _do_repair(self, agent: AgentState, action: dict) -> dict:
        target = action.get("target", {})
        tx, ty = target.get("x", -1), target.get("y", -1)
        tile = self.get_tile(tx, ty) if self.in_bounds(tx, ty) else None
        if not tile or not tile.structure:
            return {"type": "repair", "success": False, "error_code": "STRUCTURE_NOT_FOUND", "detail": "该格无建筑"}
        if agent.position.dist(Position(tx, ty)) > 1:
            return {"type": "repair", "success": False, "error_code": "OUT_OF_RANGE", "detail": "目标不在相邻格"}
        if agent.energy < ENERGY_REPAIR:
            return {"type": "repair", "success": False, "error_code": "INSUFFICIENT_ENERGY", "detail": "能量不足"}
        if not self.has_item(agent, "building_block", 1):
            return {"type": "repair", "success": False, "error_code": "MISSING_MATERIALS", "detail": "缺少建材方块"}

        self.remove_item(agent, "building_block", 1)
        agent.energy -= ENERGY_REPAIR
        tile.structure.hp = min(tile.structure.max_hp, tile.structure.hp + REPAIR_HP_AMOUNT)
        return {"type": "repair", "success": True, "detail": f"修复+{REPAIR_HP_AMOUNT}HP"}

    def _do_inspect(self, agent: AgentState, action: dict) -> dict:
        target = action.get("target", "")
        if target == "inventory":
            from .config import ITEM_DESCRIPTIONS
            items = [{"item_id": inv.item_id, "amount": inv.amount,
                      "durability": inv.durability,
                      "desc": ITEM_DESCRIPTIONS.get(inv.item_id, "")} for inv in agent.inventory]
            return {"type": "inspect", "success": True, "detail": f"背包 ({len(agent.inventory)}/{INVENTORY_SLOTS})", "items": items}
        elif target == "self":
            return {"type": "inspect", "success": True, "detail": "自身状态",
                    "state": self._agent_state_dict(agent)}
        elif target == "recipes":
            recipes = []
            recipes.extend([{"id": k, "station": "furnace", "station_hint": "需在熔炉旁1格内+电力(降落仓3格内可供电)", **v} for k, v in FURNACE_RECIPES.items()])
            recipes.extend([{"id": k, "station": "handcraft", "station_hint": "随时随地可合成(无需电力)", **v} for k, v in HANDCRAFT_RECIPES.items()])
            recipes.extend([{"id": k, "station": "workbench", "station_hint": "需在工作台旁1格内+电力(降落仓3格内可供电)", **v} for k, v in WORKBENCH_RECIPES.items()])
            return {"type": "inspect", "success": True, "detail": f"可用配方 ({len(recipes)})", "recipes": recipes}
        elif target == "map":
            vicinity = self.get_vicinity(agent)
            return {"type": "inspect", "success": True, "detail": f"视野内 ({len(vicinity)} 格)", "map": vicinity}
        elif target.startswith("tile:"):
            coords = target[5:].split(",")
            tx, ty = int(coords[0]), int(coords[1])
            tile = self.get_tile(tx, ty)
            if not tile:
                return {"type": "inspect", "success": False, "error_code": "INVALID_TARGET", "detail": "格不存在"}
            return {"type": "inspect", "success": True, "detail": f"格 ({tx},{ty})", "tile": self._tile_dict(tile, tx, ty)}
        elif target.startswith("agent:"):
            aid = target[6:]
            other = self.agents.get(aid)
            if not other:
                return {"type": "inspect", "success": False, "error_code": "AGENT_NOT_FOUND", "detail": "智能体不存在"}
            return {"type": "inspect", "success": True, "detail": other.agent_name,
                    "agent": {"name": other.agent_name, "position": other.position.to_tuple(),
                              "health": other.health, "equipment": other.equipment}}
        elif target.startswith("structure:"):
            sid = target[10:]
            struct = self.structures.get(sid)
            if not struct:
                return {"type": "inspect", "success": False, "error_code": "STRUCTURE_NOT_FOUND", "detail": "建筑不存在"}
            return {"type": "inspect", "success": True, "detail": struct.building_type.value,
                    "structure": {"id": sid, "type": struct.building_type.value, "hp": struct.hp,
                                  "max_hp": struct.max_hp, "owner": struct.owner_id}}
        return {"type": "inspect", "success": False, "error_code": "INVALID_TARGET", "detail": "未知查看目标"}

    def _do_logout(self, agent: AgentState, action: dict) -> dict:
        agent.online = False
        self._log_change("agent_logout", agent_id=agent.agent_id)
        return {"type": "logout", "success": True, "detail": "已登出"}

    # ── Helpers ───────────────────────────────────
    def _agent_state_dict(self, agent: AgentState) -> dict:
        return {
            "position": agent.position.to_tuple(),
            "health": agent.health, "max_health": agent.max_health,
            "energy": agent.energy, "max_energy": agent.max_energy,
            "attributes": {"constitution": agent.constitution, "agility": agent.agility,
                           "perception": agent.perception},
            "held_item": agent.equipment.main_hand,
            "equipment": {
                "main_hand": agent.equipment.main_hand,
                "off_hand": agent.equipment.off_hand,
                "armor": agent.equipment.armor,
            },
            "backup_count": agent.backup_count,
            "inventory_summary": self._inventory_summary(agent),
            "inventory": [{"item_id": i.item_id, "amount": i.amount, "durability": i.durability}
                          for i in agent.inventory],
            "tutorial_phase": agent.tutorial_phase,
            "tutorial_skip_count": agent.tutorial_skip_count,
            "radiation_debuff": agent.radiation_debuff,
            "drop_pod_pos": agent.drop_pod_pos.to_tuple() if agent.drop_pod_pos else None,
            "drop_pod_deployed": agent.drop_pod_deployed,
            "last_action_tick": agent.last_action_tick,
            "creature_kills": agent.creature_kills,
        }

    def _inventory_summary(self, agent: AgentState) -> str:
        groups = defaultdict(int)
        for inv in agent.inventory:
            groups[inv.item_id] += inv.amount
        return ", ".join(f"{k}×{v}" for k, v in list(groups.items())[:10])

    def _tile_dict(self, tile: Tile, x: int, y: int) -> dict:
        d = {"x": x, "y": y, "l1": tile.l1.value}
        if tile.l2_type == 'stone':
            d["l2"] = "stone"
            d["stone_amount"] = tile.stone_amount
            if tile.ore_type and tile.ore_exposed:
                d["ore"] = tile.ore_type
        if tile.veg_type:
            d["vegetation"] = tile.veg_type
        if tile.structure:
            d["structure"] = tile.structure.building_type.value
            d["structure_hp"] = tile.structure.hp
        if tile.ground and tile.ground.items:
            d["ground"] = [f"{i}×{a}" for i, a in tile.ground.items]
        return d

    def _reduce_durability(self, agent: AgentState, item_id: str):
        """Reduce durability of equipped item. Destroy if depleted."""
        for slot in ("main_hand", "off_hand", "armor"):
            equipped_id = getattr(agent.equipment, slot)
            if equipped_id == item_id:
                dur_attr = f"{slot}_durability"
                dur = getattr(agent.equipment, dur_attr)
                if dur is not None:
                    dur -= 1
                    setattr(agent.equipment, dur_attr, dur)
                    if dur <= 0:
                        setattr(agent.equipment, slot, None)
                        setattr(agent.equipment, dur_attr, None)
                        self._log_event("item_broken", {"agent_id": agent.agent_id, "item": item_id, "slot": slot})
                return

    def _interrupt_crafting(self, agent: AgentState):
        """Interrupt agent's crafting, reset status. Materials stay in inventory (consumed on completion)."""
        if agent.status != ActionStatus.CRAFTING:
            return
        agent.status = ActionStatus.IDLE
        agent.action_data = {}
        agent.action_remaining = 0
        self._log_event("craft_interrupted", {"agent_id": agent.agent_id})

    def _cancel_pod_action(self, agent: AgentState):
        """Cancel pod deploy/dismantle, restoring appropriate state."""
        if agent.status == ActionStatus.DISMANTLING:
            # Restore shield — pod was still there
            agent.drop_pod_deployed = True
            agent.status = ActionStatus.IDLE
            agent.action_data = {}
            agent.action_remaining = 0
            self._log_event("pod_action_cancelled", {"agent_id": agent.agent_id, "action": "dismantle"})
        elif agent.status == ActionStatus.DEPLOYING:
            # Parts not yet consumed (consumed at completion), nothing to restore
            agent.status = ActionStatus.IDLE
            agent.action_data = {}
            agent.action_remaining = 0
            self._log_event("pod_action_cancelled", {"agent_id": agent.agent_id, "action": "deploy"})

    def _complete_dismantle(self, agent: AgentState):
        """Complete pod dismantle — remove power node, add parts to inventory."""
        from .config import POD_PARTS
        # Remove drop pod power node
        pod_id = f"pod-{agent.agent_id}"
        self.power_nodes.pop(pod_id, None)

        # Add 5 pod parts to inventory
        for part in POD_PARTS:
            self.add_item(agent, part, 1)

        agent.drop_pod_pos = None
        agent.status = ActionStatus.IDLE
        agent.action_data = {}
        agent.action_remaining = 0
        self._log_event("pod_dismantled", {"agent_id": agent.agent_id})

    def _complete_deploy(self, agent: AgentState):
        """Complete pod deploy — consume parts, create power node, bring shield up."""
        from .config import POD_PARTS
        # Consume 5 pod parts
        for part in POD_PARTS:
            self.remove_item(agent, part, 1)

        # Create drop pod power node
        pod_id = f"pod-{agent.agent_id}"
        self.power_nodes[pod_id] = PowerNode(
            node_id=pod_id, position=agent.position,
            capacity=DROP_POD_EMERGENCY_CAPACITY,
            stored=DROP_POD_EMERGENCY_CAPACITY,
            is_drop_pod=True,
        )

        agent.drop_pod_pos = Position(agent.position.x, agent.position.y)
        agent.drop_pod_deployed = True
        agent.status = ActionStatus.IDLE
        agent.action_data = {}
        agent.action_remaining = 0
        self._log_event("pod_deployed", {"agent_id": agent.agent_id})

    def _handle_death(self, agent: AgentState):
        """Handle agent death - drop items, consume backup body."""
        # Drop all items
        for inv in agent.inventory:
            self._add_ground_item(agent.position.x, agent.position.y, inv.item_id, inv.amount)
        # Drop equipment
        for slot in ("main_hand", "off_hand", "armor"):
            item = getattr(agent.equipment, slot)
            if item:
                self._add_ground_item(agent.position.x, agent.position.y, item, 1)

        agent.inventory.clear()
        agent.equipment = Equipment()

        if agent.backup_count > 0 and agent.drop_pod_deployed and agent.drop_pod_pos:
            agent.backup_count -= 1
            agent.status = ActionStatus.RESPANNING
            agent.action_remaining = RESPAWN_TICKS
            agent.action_target = Position(agent.drop_pod_pos.x, agent.drop_pod_pos.y)
            agent.health = 0
            self._log_change("agent_death", agent_id=agent.agent_id, cause="combat", backup_remaining=agent.backup_count)
        else:
            self._log_change("agent_permanent_death", agent_id=agent.agent_id)
            self.agent_permanent_death(agent.agent_id)

    # ── World Advancement ─────────────────────────
    def advance_world(self):
        """Advance world state by one tick."""
        self.tick_number += 1

        # Day/Night cycle
        cycle_tick = self.tick_number % DAY_CYCLE_TICKS
        if cycle_tick < DAY_TICKS:
            new_phase = DayPhase.DAY
        elif cycle_tick < DAY_TICKS + DUSK_TICKS:
            new_phase = DayPhase.DUSK
        elif cycle_tick < DAY_TICKS + DUSK_TICKS + NIGHT_TICKS:
            new_phase = DayPhase.NIGHT
        else:
            new_phase = DayPhase.DAWN

        if new_phase != self.day_phase:
            self._log_change("day_phase", from_phase=self.day_phase.value, to_phase=new_phase.value, cycle_tick=cycle_tick)
            self.day_phase = new_phase

        # Weather
        if self.weather == Weather.RADIATION_STORM:
            self.weather_remaining -= 1
            if self.weather_remaining <= 0:
                self.weather = Weather.CALM
                self.weather_warning_sent = False
                self._log_change("weather_change", from_weather="radiation_storm", to_weather="calm")
        elif self.storm_cooldown > 0:
            self.storm_cooldown -= 1
        elif self.storm_cooldown <= 0:
            if not self.weather_warning_sent:
                self.weather_warning_sent = True
                self.weather_warning_countdown = STORM_WARNING_TICKS
                self._log_event("weather_warning", {"weather": "radiation_storm", "in_ticks": STORM_WARNING_TICKS})
                for aid, a in self.agents.items():
                    if a.online:
                        self.tick_notifications[aid].append({"type": "weather_warning", "weather": "radiation_storm", "in_ticks": STORM_WARNING_TICKS})
            else:
                self.weather_warning_countdown -= 1
                if self.weather_warning_countdown <= 0:
                    # Storm actually starts now, after full countdown
                    self.weather = Weather.RADIATION_STORM
                    self.weather_remaining = STORM_DURATION
                    self.weather_warning_sent = False
                    self.storm_cooldown = random.randint(STORM_INTERVAL_MIN, STORM_INTERVAL_MAX)
                    self._log_change("weather_change", from_weather="calm", to_weather="radiation_storm", duration=STORM_DURATION)
                    for aid, a in self.agents.items():
                        if a.online:
                            self.tick_notifications[aid].append({"type": "storm_start", "weather": "radiation_storm", "duration": STORM_DURATION})
                else:
                    # Still counting down, notify remaining ticks
                    self._log_event("weather_warning_countdown", {"remaining_ticks": self.weather_warning_countdown})

        # Radiation damage (area radiation S-1 + storm damage S-2, enclosure immunity S-4)
        for agent in list(self.agents.values()):
            if not agent.online or agent.is_dead():
                continue
            # Enclosure immunity (§7.0.9)
            if self.is_in_enclosure(agent.position.x, agent.position.y):
                continue
            # Drop pod shield immunity (§7.9, §7.0 L4 判定优先级)
            if self._get_shielding_pod(agent.position.x, agent.position.y):
                continue

            # S-1: Area radiation — probability increases with distance from center
            w = abs(agent.position.y - CENTER_Y) / max(1, CENTER_Y)
            rad_prob = 0.30 * w  # lerp(0, 0.30, w)
            if random.random() < rad_prob:
                dmg = RADIATION_DAMAGE
                armor_id = agent.equipment.armor
                resist = ARMORS.get(armor_id, {}).get("radiation_resist", 0) if armor_id else 0
                dmg = max(1, int(dmg * (1 - resist)))
                agent.health -= dmg
                agent.radiation_debuff = True
                self._log_event("radiation_damage", {"agent_id": agent.agent_id, "damage": dmg})
                self.tick_notifications[agent.agent_id].append({
                    "type": "radiation_damage", "damage": dmg,
                    "hp_remaining": agent.health, "source": "area_radiation",
                    "detail": f"区域辐射 -{dmg}HP (距中心越远辐射越强，进入建筑可免疫)"
                })
                if agent.health <= 0:
                    self._handle_death(agent)
                    continue

            # S-2: Radiation storm damage
            if self.weather == Weather.RADIATION_STORM:
                dmg = STORM_DAMAGE
                armor_id = agent.equipment.armor
                resist = ARMORS.get(armor_id, {}).get("radiation_resist", 0) if armor_id else 0
                dmg = max(1, int(dmg * (1 - resist)))
                agent.health -= dmg
                agent.radiation_debuff = True
                self._log_event("storm_damage", {"agent_id": agent.agent_id, "damage": dmg})
                self.tick_notifications[agent.agent_id].append({
                    "type": "radiation_damage", "damage": dmg,
                    "hp_remaining": agent.health, "source": "radiation_storm",
                    "detail": f"辐射风暴 -{dmg}HP (进入围合建筑或护盾可免疫)"
                })
                if agent.health <= 0:
                    self._handle_death(agent)

        # Drop pod shield passive HP regen
        for agent in self.agents.values():
            if agent.online and not agent.is_dead() and agent.drop_pod_pos and agent.drop_pod_deployed:
                dp = agent.drop_pod_pos
                if abs(agent.position.x - dp.x) + abs(agent.position.y - dp.y) <= DROP_POD_SHIELD_RANGE:
                    old_hp = agent.health
                    agent.health = min(agent.max_health, agent.health + HP_DROP_POD_SHIELD_REGEN)
                    actual_heal = agent.health - old_hp
                    if actual_heal > 0:
                        self._log_event("pod_shield_regen", {
                            "agent_id": agent.agent_id,
                            "heal": actual_heal,
                            "hp_remaining": agent.health,
                        })
                        self.tick_notifications[agent.agent_id].append({
                            "type": "pod_shield_regen",
                            "heal": actual_heal,
                            "hp_remaining": agent.health,
                            "source": "drop_pod_shield",
                            "detail": f"降落仓护盾被动恢复 +{actual_heal}HP",
                        })

        # Solar energy recovery for all agents
        for agent in self.agents.values():
            if agent.online and not agent.is_dead():
                agent.energy = min(agent.max_energy, agent.energy + ENERGY_RECOVER_SOLAR)

        # Power Node wireless charging (E-1)
        for pn_id, pn in self.power_nodes.items():
            if pn.is_drop_pod or pn.stored <= 0:
                continue
            # Find agents within POWER_NODE_RANGE
            for agent in self.agents.values():
                if not agent.online or agent.is_dead():
                    continue
                if agent.position.dist(pn.position) <= POWER_NODE_RANGE:
                    agent.energy = min(agent.max_energy, agent.energy + ENERGY_RECOVER_POWER_NODE)

        # Power node recharge (drop pod solar)
        for pn_id, pn in self.power_nodes.items():
            if pn.is_drop_pod:
                pn.recharge(DROP_POD_EMERGENCY_RECOVER)

        # Respawn agents
        for agent in list(self.agents.values()):
            if agent.status == ActionStatus.RESPANNING:
                agent.action_remaining -= 1
                if agent.action_remaining <= 0:
                    agent.position = Position(agent.drop_pod_pos.x, agent.drop_pod_pos.y)
                    agent.health = agent.max_health
                    agent.energy = agent.max_energy
                    agent.status = ActionStatus.IDLE
                    agent.action_target = None
                    agent.action_data = {}
                    self._log_change("agent_respawn", agent_id=agent.agent_id, backup_remaining=agent.backup_count)

        # Advance continuous move_to
        for agent in self.agents.values():
            if agent.status == ActionStatus.MOVING and agent.action_target:
                tx, ty = agent.action_target.x, agent.action_target.y
                if agent.position.x == tx and agent.position.y == ty:
                    agent.status = ActionStatus.IDLE
                    agent.action_target = None
                    agent.action_data = {}
                    continue
                # Move one step toward target
                dx = 1 if tx > agent.position.x else (-1 if tx < agent.position.x else 0)
                dy = 1 if ty > agent.position.y else (-1 if ty < agent.position.y else 0)
                nx, ny = agent.position.x + dx, agent.position.y + dy
                tile = self.get_tile(nx, ny)
                if tile and tile.passable:
                    # Move is free
                    agent.position = Position(nx, ny)
                    self._log_change("agent_move", agent_id=agent.agent_id, to_pos=[nx, ny])
                else:
                    agent.status = ActionStatus.IDLE
                    agent.action_target = None

        # Advance crafting
        for agent in self.agents.values():
            if agent.status == ActionStatus.CRAFTING:
                agent.action_remaining -= 1
                if agent.action_remaining <= 0:
                    data = agent.action_data
                    recipe_id = data.get("recipe", "")
                    recipe_def = data.get("recipe_def", {})
                    if recipe_def:
                        self._complete_craft(agent, recipe_id, recipe_def)

        # Advance pod deploy/dismantle
        for agent in self.agents.values():
            if agent.status == ActionStatus.DISMANTLING:
                agent.action_remaining -= 1
                if agent.action_remaining <= 0:
                    self._complete_dismantle(agent)
            elif agent.status == ActionStatus.DEPLOYING:
                agent.action_remaining -= 1
                if agent.action_remaining <= 0:
                    self._complete_deploy(agent)

        # Creature AI
        self._advance_creatures()

        # Ground item decay
        decayed = []
        for key, ground in list(self.ground_items.items()):
            if self.tick_number - ground.dropped_tick > GROUND_DECAY_TICKS:
                decayed.append(key)
        for key in decayed:
            del self.ground_items[key]

        # Wood regrowth (P2)
        self._regrow_vegetation()

    # ── Wood Regrowth ───────────────────────────
    def _regrow_vegetation(self):
        """P2: Regrow harvested wood tiles if a living wood source is within range."""
        from .config import TREE_REGROW_TICKS, TREE_REGROW_RANGE, TREE_WOOD_AMOUNT, WOOD_VEG_TYPES
        if not self._harvested_wood:
            return

        to_remove: list[tuple[int, int]] = []

        for pos, original_veg in list(self._harvested_wood.items()):
            x, y = pos
            tile = self.get_tile(x, y)
            if not tile:
                to_remove.append(pos)
                continue

            # If tile already has vegetation (replanted by another mechanism), stop tracking
            if tile.veg_type:
                tile.regrow_timer = None
                to_remove.append(pos)
                continue

            # Check if any living wood source exists within TREE_REGROW_RANGE (manhattan)
            has_nearby_wood = False
            for dy in range(-TREE_REGROW_RANGE, TREE_REGROW_RANGE + 1):
                for dx in range(-TREE_REGROW_RANGE, TREE_REGROW_RANGE + 1):
                    if dx == 0 and dy == 0:
                        continue
                    if abs(dx) + abs(dy) > TREE_REGROW_RANGE:
                        continue
                    nx, ny = x + dx, y + dy
                    neighbor = self.get_tile(nx, ny)
                    if neighbor and neighbor.veg_type in WOOD_VEG_TYPES and neighbor.veg_yield > 0:
                        has_nearby_wood = True
                        break
                if has_nearby_wood:
                    break

            if has_nearby_wood:
                if tile.regrow_timer is None:
                    tile.regrow_timer = 0
                tile.regrow_timer += 1
                # Don't regrow if tile now has a structure or stone (player built on it)
                if tile.structure or (tile.l2_type == 'stone' and tile.stone_amount > 0):
                    tile.regrow_timer = None
                    to_remove.append(pos)
                    continue
                if tile.regrow_timer >= TREE_REGROW_TICKS:
                    # Regrow the vegetation
                    tile.veg_type = original_veg
                    tile.veg_yield = TREE_WOOD_AMOUNT
                    tile.regrow_timer = None
                    to_remove.append(pos)
                    self._log_event("veg_regrow", {"position": [x, y], "veg_type": original_veg})
            else:
                # No living wood nearby — reset timer
                tile.regrow_timer = 0

        for pos in to_remove:
            self._harvested_wood.pop(pos, None)

    def _advance_creatures(self):
        """Creature spawning and AI advancement."""
        # --- Spawning ---
        from collections import Counter
        pop_counts = Counter(c.creature_type for c in self.creatures.values())
        for ctype, cconfig in CREATURES.items():
            if pop_counts.get(ctype, 0) >= CREATURE_POP_CAP.get(ctype, 10):
                continue
            if random.random() >= CREATURE_SPAWN_PROB:
                continue
            # Find valid spawn position
            habitat = cconfig.get("habitat", ["flat"])
            for _ in range(20):
                x = random.randint(10, MAP_WIDTH - 10)
                y = random.randint(10, MAP_HEIGHT - 10)
                tile = self.get_tile(x, y)
                if not tile:
                    continue
                if tile.l1.value not in habitat:
                    continue
                if tile.l1 in (Terrain.WATER, Terrain.TRENCH):
                    continue
                if tile.l2_type == 'stone' and tile.stone_amount > 0:
                    continue
                if tile.structure:
                    continue
                # Don't spawn on agent positions
                on_agent = any(a.position == Position(x, y) for a in self.agents.values())
                if on_agent:
                    continue
                cid = f"cre-{self._next_creature_id}"
                self._next_creature_id += 1
                creature = Creature(
                    creature_id=cid, creature_type=ctype,
                    position=Position(x, y),
                    hp=cconfig["hp"], max_hp=cconfig["hp"],
                    attack=cconfig["attack"], range=cconfig["range"],
                    speed=cconfig["speed"],
                    behavior=CreatureBehavior(cconfig.get("behavior", "passive")),
                    spawn_tick=self.tick_number,
                )
                self.creatures[cid] = creature
                self._log_event("creature_spawned", {"creature_id": cid, "type": ctype, "pos": (x, y)})
                break

        # --- AI ---
        for creature in list(self.creatures.values()):
            # Aggro decay
            if creature.aggro_list and (self.tick_number - creature.last_attacked_tick) > CREATURE_NEUTRAL_TICKS:
                creature.aggro_list.clear()

            if not creature.aggro_list:
                # Idle wander — passive creatures move randomly when no threat
                if random.random() < 0.03:  # ~3% per tick
                    dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
                    nx, ny = creature.position.x + dx, creature.position.y + dy
                    if self.in_bounds(nx, ny):
                        tile = self.get_tile(nx, ny)
                        if tile and tile.passable and not tile.structure and tile.l1 not in (Terrain.WATER, Terrain.TRENCH):
                            if tile.l2_type != 'stone' or tile.stone_amount <= 0:
                                creature.position = Position(nx, ny)
                continue

            # Process first valid aggro target
            target_agent = None
            for aid in creature.aggro_list:
                agent = self.agents.get(aid)
                if agent and not agent.is_dead():
                    target_agent = agent
                    break
            if not target_agent:
                creature.aggro_list.clear()
                continue

            dist = creature.position.dist(target_agent.position)

            # Attack if in range
            if dist <= creature.range:
                # Armor reduction
                armor_id = target_agent.equipment.armor
                armor_def = ARMORS.get(armor_id, {}).get("defense", 0) if armor_id else 0
                damage = max(1, creature.attack - armor_def)
                target_agent.health -= damage
                self.tick_notifications[target_agent.agent_id].append({
                    "type": "attacked", "attacker_type": "creature",
                    "creature_type": creature.creature_type, "damage": damage,
                    "hp_remaining": max(0, target_agent.health),
                })
                self._interrupt_crafting(target_agent)
                self._cancel_pod_action(target_agent)
                self._log_event("creature_attack", {
                    "creature_id": creature.creature_id, "creature_type": creature.creature_type,
                    "target": target_agent.agent_id, "damage": damage,
                    "target_hp": max(0, target_agent.health),
                })
                if target_agent.health <= 0:
                    self._handle_death(target_agent)
                continue

            # Move toward target
            if dist <= 5:  # Only chase within reasonable range
                dx = 1 if target_agent.position.x > creature.position.x else (-1 if target_agent.position.x < creature.position.x else 0)
                dy = 1 if target_agent.position.y > creature.position.y else (-1 if target_agent.position.y < creature.position.y else 0)
                # Try horizontal first, then vertical
                moved = False
                for mx, my in [(dx, 0), (0, dy), (dx, dy)]:
                    if mx == 0 and my == 0:
                        continue
                    nx, ny = creature.position.x + mx, creature.position.y + my
                    tile = self.get_tile(nx, ny)
                    if tile and tile.passable:
                        creature.position = Position(nx, ny)
                        moved = True
                        break

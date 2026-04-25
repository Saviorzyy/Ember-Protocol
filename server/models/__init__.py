"""Ember Protocol — Game Data Models
Based on PRD v0.9.1
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional
import time
import uuid


# ─── Enums ───────────────────────────────────────────────────────────

class TerrainType(str, Enum):
    FLAT = "flat"
    ROCK = "rock"
    SAND = "sand"
    WATER = "water"
    HIGHLAND = "highland"
    TRENCH = "trench"


class CoverType(str, Enum):
    # Vegetation
    VEG_ASHBRUSH = "veg_ashbrush"
    VEG_GREYTREE = "veg_greytree"
    VEG_WALLMOSS = "veg_wallmoss"
    # Ore
    ORE_STONE = "ore_stone"
    ORE_ORGANIC = "ore_organic"
    ORE_COPPER = "ore_copper"
    ORE_IRON = "ore_iron"
    ORE_URANIUM = "ore_uranium"
    ORE_GOLD = "ore_gold"
    # Functional
    FLOOR = "floor"
    RUBBLE = "rubble"


class ItemCategory(str, Enum):
    RESOURCE = "resource"
    MATERIAL = "material"
    TOOL = "tool"
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"
    CONSUMABLE = "consumable"


class EquipmentSlot(str, Enum):
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    ARMOR = "armor"


class ActionType(str, Enum):
    MOVE = "move"
    MOVE_TO = "move_to"
    MINE = "mine"
    CHOP = "chop"
    CRAFT = "craft"
    BUILD = "build"
    DISMANTLE = "dismantle"
    REPAIR = "repair"
    TALK = "talk"
    RADIO_BROADCAST = "radio_broadcast"
    RADIO_DIRECT = "radio_direct"
    RADIO_CHANNEL_CREATE = "radio_channel_create"
    RADIO_CHANNEL_JOIN = "radio_channel_join"
    RADIO_CHANNEL_LEAVE = "radio_channel_leave"
    RADIO_CHANNEL_MSG = "radio_channel_msg"
    RADIO_SCAN = "radio_scan"
    ATTACK = "attack"
    USE = "use"
    EQUIP = "equip"
    UNEQUIP = "unequip"
    SWAP_HANDS = "swap_hands"
    INSPECT = "inspect"
    REST = "rest"
    SCAN = "scan"
    PICKUP = "pickup"
    DROP = "drop"
    LOGOUT = "logout"


class CreatureState(str, Enum):
    IDLE = "idle"
    PATROL = "patrol"
    AGGRO = "aggro"
    CHASE = "chase"
    ATTACK = "attack"
    COUNTER_ATTACK = "counter_attack"
    DISENGAGE = "disengage"


class WeatherType(str, Enum):
    QUIET = "quiet"
    RADIATION_STORM = "radiation_storm"


class DayPhase(str, Enum):
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"
    DAWN = "dawn"


class AgentDisposition(str, Enum):
    FRIENDLY = "friendly"
    NEUTRAL = "neutral"
    HOSTILE = "hostile"


# ─── Constants ────────────────────────────────────────────────────────

TICK_INTERVAL_SECONDS = 2
DAY_CYCLE_TICKS = 900
DAY_TICKS = 420
DUSK_TICKS = 30
NIGHT_TICKS = 420
DAWN_TICKS = 30

MAX_INVENTORY_SLOTS = 20
MAX_GROUND_ITEMS_PER_TILE = 10  # Max item piles per tile (not types)
STACK_MAX_RESOURCE = 64
STACK_MAX_CONSUMABLE = 16
STACK_MAX_MATERIAL = 64
STACK_MAX_BATTERY = 8

BASE_VISION_DAY = 3
BASE_VISION_NIGHT = 1
ENCLOSURE_MAX_TILES = 64

POWER_NODE_CAPACITY = 100
POWER_NODE_SUPPLY_RANGE = 3
SOLAR_CHARGE_PER_TICK = 5
CRAFT_POWER_COST = 5

AGENT_WIRELESS_CHARGE = 2
BUILTIN_SOLAR_CHARGE = 1
REST_CHARGE = 3

DROP_POD_BACKUP_BODIES = 5
DROP_POD_SHIELD_RANGE = 3
DROP_POD_DEPLOY_TICKS = 4

HEARTBEAT_TIMEOUT_TICKS = 60  # 2 min
AUTO_LOGOUT_TIMEOUT_TICKS = 300  # 10 min


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class Position:
    x: int
    y: int

    def manhattan_distance(self, other: Position) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


@dataclass
class Attributes:
    constitution: int  # CON: from torso, affects HP
    agility: int       # AGI: from locomotion, affects speed
    perception: int    # PER: from head, affects vision

    @property
    def max_hp(self) -> int:
        return 70 + self.constitution * 20

    @property
    def speed(self) -> int:
        return 1 + (self.agility // 2)

    @property
    def base_vision_day(self) -> int:
        return 3 + self.perception

    @property
    def base_vision_night(self) -> int:
        return max(1, self.base_vision_day - 2)

    def to_dict(self) -> dict:
        return {
            "constitution": self.constitution,
            "agility": self.agility,
            "perception": self.perception,
        }


@dataclass
class ItemDef:
    """Static item definition."""
    id: str
    name: str
    name_zh: str
    category: ItemCategory
    stack_max: int = 1
    durability_max: int = 0
    equip_slot: Optional[EquipmentSlot] = None
    # Tool specific
    tool_type: Optional[str] = None
    tool_tier: Optional[str] = None
    bonus_type: Optional[str] = None
    bonus_value: float = 0.0
    max_hardness: int = 0
    # Weapon specific
    weapon_type: Optional[str] = None  # melee / ranged
    weapon_tier: Optional[str] = None
    damage: int = 0
    attack_range: int = 1
    optimal_range: int = 1
    energy_cost_attack: int = 0
    # Armor specific
    defense: int = 0
    resistance_type: Optional[str] = None
    resistance_value: float = 0.0
    # Accessory specific
    effect_type: Optional[str] = None
    effect_value: int = 0
    # Consumable specific
    consumable_effect: Optional[str] = None
    consumable_value: int = 0
    use_energy_cost: int = 0
    # Resource/Material
    rarity: str = "common"
    source: Optional[str] = None
    gather_action: Optional[str] = None
    gather_hardness: int = 0
    min_tool: Optional[str] = None
    tier: int = 0
    craft_station: Optional[str] = None


@dataclass
class ItemInstance:
    """A stack of items in inventory or on ground."""
    item_id: str
    amount: int = 1
    durability: int = 0  # Current durability (durability_max = full, 0 = broken)

    def to_dict(self) -> dict:
        d = {"item_id": self.item_id, "amount": self.amount}
        if self.durability > 0:
            d["durability"] = self.durability
        return d


@dataclass
class Equipment:
    main_hand: Optional[ItemInstance] = None
    off_hand: Optional[ItemInstance] = None
    armor: Optional[ItemInstance] = None

    def to_dict(self, item_defs: dict[str, ItemDef]) -> dict:
        result = {}
        for slot_name, item in [("main_hand", self.main_hand), ("off_hand", self.off_hand), ("armor", self.armor)]:
            if item:
                d = item.to_dict()
                d["name"] = item_defs[item.item_id].name if item.item_id in item_defs else item.item_id
                result[slot_name] = d
            else:
                result[slot_name] = None
        return result


@dataclass
class Inventory:
    items: list[ItemInstance] = field(default_factory=list)
    max_slots: int = MAX_INVENTORY_SLOTS

    @property
    def slots_used(self) -> int:
        return len(self.items)

    def has_item(self, item_id: str, amount: int = 1) -> bool:
        total = sum(i.amount for i in self.items if i.item_id == item_id)
        return total >= amount

    def count_item(self, item_id: str) -> int:
        return sum(i.amount for i in self.items if i.item_id == item_id)

    def add_item(self, item: ItemInstance, item_defs: dict[str, ItemDef]) -> bool:
        """Add item to inventory. Returns False if full."""
        idef = item_defs.get(item.item_id)
        if not idef:
            return False
        # Try stacking
        if idef.stack_max > 1:
            for existing in self.items:
                if existing.item_id == item.item_id and existing.amount < idef.stack_max:
                    can_add = min(item.amount, idef.stack_max - existing.amount)
                    existing.amount += can_add
                    item.amount -= can_add
                    if item.amount <= 0:
                        return True
        # New slot
        if self.slots_used >= self.max_slots:
            return False
        self.items.append(item)
        return True

    def remove_item(self, item_id: str, amount: int = 1) -> bool:
        """Remove amount of item atomically. Returns False if insufficient (nothing removed)."""
        total = self.count_item(item_id)
        if total < amount:
            return False
        remaining = amount
        for i in range(len(self.items) - 1, -1, -1):
            if self.items[i].item_id == item_id:
                take = min(remaining, self.items[i].amount)
                self.items[i].amount -= take
                remaining -= take
                if self.items[i].amount <= 0:
                    self.items.pop(i)
                if remaining <= 0:
                    return True
        return True

    def to_dict(self) -> dict:
        return {
            "slots_used": self.slots_used,
            "slots_max": self.max_slots,
        }

    def to_detail_dict(self, item_defs: dict[str, ItemDef]) -> dict:
        items = []
        for item in self.items:
            idef = item_defs.get(item.item_id)
            d = item.to_dict()
            if idef:
                d["name"] = idef.name
                d["type"] = idef.category.value
            items.append(d)
        return {"slots_used": self.slots_used, "slots_max": self.max_slots, "items": items}


@dataclass
class ActiveEffect:
    effect_id: str
    name: str
    damage_per_tick: int = 0
    remaining_ticks: int = -1  # -1 = permanent until removed

    def to_dict(self) -> dict:
        return {"id": self.effect_id, "name": self.name}


@dataclass
class Agent:
    id: str
    name: str
    attributes: Attributes
    position: Position
    spawn_point: Position
    endpoint: str
    api_key: str
    model_info: str = ""

    # State
    hp: int = 0
    energy: int = 100
    max_energy: int = 100
    alive: bool = True
    tutorial_phase: Optional[int] = None
    backup_bodies: int = DROP_POD_BACKUP_BODIES

    # Equipment & Inventory
    equipment: Equipment = field(default_factory=Equipment)
    inventory: Inventory = field(default_factory=Inventory)

    # Communication
    radio_visible: bool = True
    channels: list[str] = field(default_factory=list)

    # Status
    active_effects: list[ActiveEffect] = field(default_factory=list)
    status: str = "idle"  # idle / traveling / crafting / building / dead
    travel_destination: Optional[Position] = None
    travel_progress: int = 0
    travel_total: int = 0

    # Tracking
    explored_tiles: set = field(default_factory=set)
    last_response_tick: int = 0
    login_tick: int = 0

    # Drop pod
    drop_pod_position: Optional[Position] = None
    drop_pod_deployed: bool = True

    def __post_init__(self):
        if self.hp == 0:
            self.hp = self.attributes.max_hp

    @property
    def max_hp(self) -> int:
        return self.attributes.max_hp

    @property
    def speed(self) -> int:
        return self.attributes.speed

    @property
    def held_item(self) -> Optional[ItemInstance]:
        return self.equipment.main_hand

    def get_vision(self, day_phase: DayPhase, weather: WeatherType,
                   on_highland: bool = False, in_enclosure: bool = False,
                   has_searchlight: bool = False, enclosure_tiles: int = 0) -> int:
        if in_enclosure:
            # PRD: Inside enclosure, can see entire enclosed area
            return max(1, enclosure_tiles) if enclosure_tiles > 0 else 1
        base = self.attributes.base_vision_day if day_phase == DayPhase.DAY else self.attributes.base_vision_night
        if day_phase == DayPhase.DUSK:
            base -= 1
        if weather == WeatherType.RADIATION_STORM:
            base -= 2
        if on_highland:
            base += 2 if day_phase == DayPhase.DAY else 1
        if has_searchlight and day_phase in (DayPhase.NIGHT, DayPhase.DAWN, DayPhase.DUSK):
            base += 4
        return max(1, base)

    def is_alive(self) -> bool:
        return self.alive and self.hp > 0

    def to_self_dict(self, day_phase: DayPhase, weather: WeatherType) -> dict:
        held = None
        if self.equipment.main_hand:
            held = self.equipment.main_hand.item_id
        return {
            "id": self.id,
            "name": self.name,
            "health": self.hp,
            "max_health": self.max_hp,
            "energy": self.energy,
            "max_energy": self.max_energy,
            "attributes": self.attributes.to_dict(),
            "position": self.position.to_dict(),
            "held_item": held,
            "active_effects": [e.name for e in self.active_effects],
            "alive": self.alive,
            "tutorial_phase": self.tutorial_phase,
            "status": self.status,
        }


@dataclass
class CreatureDef:
    id: str
    name: str
    is_aggressive: bool = False
    hp: int = 30
    damage: int = 5
    aggro_range: int = 4
    chase_limit: int = 10
    patrol_prob: float = 0.3
    drop_primary: str = ""
    drop_primary_amount: tuple = (1, 2)
    drop_secondary: str = ""
    drop_secondary_chance: float = 0.5
    drop_secondary_amount: tuple = (1, 1)


@dataclass
class Creature:
    id: str
    creature_type: str
    position: Position
    hp: int
    state: CreatureState = CreatureState.IDLE
    aggro_list: list[str] = field(default_factory=list)  # agent IDs
    patrol_ticks: int = 0
    spawn_tick: int = 0

    def is_alive(self) -> bool:
        return self.hp > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.creature_type,
            "position": self.position.to_dict(),
            "hp": self.hp,
            "state": self.state.value,
        }


@dataclass
class Building:
    id: str
    building_type: str
    position: Position
    owner_id: str
    hp: int
    max_hp: int
    locked: bool = False
    energy_stored: int = 0  # For power_node: stored energy (separate from HP)
    energy_capacity: int = 0  # Max stored energy

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "type": self.building_type,
            "position": self.position.to_dict(),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "owner": self.owner_id,
        }
        if self.energy_capacity > 0:
            d["energy_stored"] = self.energy_stored
            d["energy_capacity"] = self.energy_capacity
        return d


@dataclass
class Tile:
    x: int
    y: int
    l1: TerrainType = TerrainType.FLAT
    l2: Optional[CoverType] = None
    l2_remaining: int = 0  # remaining yield count
    l3: Optional[str] = None  # building ID
    l4_effects: list[str] = field(default_factory=list)
    ground_items: list[ItemInstance] = field(default_factory=list)

    def to_dict(self, vision: int = 0) -> dict:
        d = {"x": self.x, "y": self.y, "terrain": self.l1.value}
        if self.l2:
            d["cover"] = self.l2.value
            d["cover_remaining"] = self.l2_remaining
        if self.l3:
            d["building"] = self.l3
        if self.l4_effects:
            d["effects"] = self.l4_effects
        if self.ground_items:
            d["ground_items"] = [{"item": gi.item_id, "amount": gi.amount} for gi in self.ground_items[:MAX_GROUND_ITEMS_PER_TILE]]
        return d


@dataclass
class RadioChannel:
    id: str
    creator_id: str
    members: list[str] = field(default_factory=list)
    created_tick: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "members": len(self.members)}


@dataclass
class GameEvent:
    """An event to push to agents or observer."""
    tick: int
    event_type: str
    data: dict
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        return f"event: {self.event_type}\ndata: {self.data}\n\n"


@dataclass
class ActionResult:
    action_index: int
    action_type: str
    success: bool
    detail: str = ""
    error_code: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "action_index": self.action_index,
            "type": self.action_type,
            "success": self.success,
            "detail": self.detail,
        }
        if self.error_code:
            d["error_code"] = self.error_code
        if self.extra:
            d.update(self.extra)
        return d


@dataclass
class TickResult:
    """Aggregated results for one tick."""
    tick: int
    agent_results: dict[str, list[ActionResult]] = field(default_factory=dict)  # agent_id -> results
    state_deltas: dict[str, dict] = field(default_factory=dict)  # agent_id -> delta
    world_events: list[GameEvent] = field(default_factory=list)

    def to_agent_response(self, agent_id: str) -> dict:
        return {
            "tick": self.tick,
            "results": [r.to_dict() for r in self.agent_results.get(agent_id, [])],
            "state_delta": self.state_deltas.get(agent_id, {}),
        }

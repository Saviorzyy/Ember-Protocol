"""Ember Protocol — Data Models (MVP v1.3.0)"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import hashlib
import secrets


# ── Enums ────────────────────────────────────────
class Terrain(str, Enum):
    FLAT = "flat"; SAND = "sand"; ROCK = "rock"
    WATER = "water"; TRENCH = "trench"

class L2Cover(str, Enum):
    STONE = "stone"; ASHBUSH = "ashbush"
    GREYTREE = "greytree"; WALLMOSS = "wallmoss"
    FLOOR = "floor"; RUBBLE = "rubble"

class BuildingType(str, Enum):
    WALL = "wall"; DOOR = "door"
    WORKBENCH = "workbench"; FURNACE = "furnace"
    POWER_NODE = "power_node"

class DayPhase(str, Enum):
    DAY = "day"; DUSK = "dusk"; NIGHT = "night"; DAWN = "dawn"

class Weather(str, Enum):
    CALM = "calm"; RADIATION_STORM = "radiation_storm"

class CreatureBehavior(str, Enum):
    PASSIVE = "passive"

class ActionStatus(str, Enum):
    IDLE = "idle"; MOVING = "moving_to"; CRAFTING = "crafting"
    DEPLOYING = "deploying"; DISMANTLING = "dismantling"
    RESPANNING = "respawning"


# ── Data Classes ─────────────────────────────────
@dataclass
class Position:
    x: int; y: int

    def __hash__(self): return hash((self.x, self.y))
    def __eq__(self, o): return isinstance(o, Position) and self.x == o.x and self.y == o.y

    def dist(self, other: Position) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def to_tuple(self): return (self.x, self.y)

    @staticmethod
    def from_tuple(t): return Position(t[0], t[1])


@dataclass
class InventoryItem:
    item_id: str; amount: int = 1
    durability: Optional[int] = None


@dataclass
class Equipment:
    main_hand: Optional[str] = None
    off_hand: Optional[str] = None
    armor: Optional[str] = None
    main_hand_durability: Optional[int] = None
    off_hand_durability: Optional[int] = None
    armor_durability: Optional[int] = None


@dataclass
class AgentState:
    agent_id: str
    agent_name: str
    position: Position
    health: int; max_health: int
    energy: int; max_energy: int = 100
    constitution: int = 1; agility: int = 1; perception: int = 1
    inventory: list[InventoryItem] = field(default_factory=list)
    equipment: Equipment = field(default_factory=Equipment)
    backup_count: int = 5
    drop_pod_pos: Optional[Position] = None
    drop_pod_deployed: bool = True
    tutorial_phase: Optional[int] = 0
    tutorial_skip_count: int = 0
    status: ActionStatus = ActionStatus.IDLE
    action_target: Optional[Position] = None
    action_remaining: int = 0
    action_data: dict = field(default_factory=dict)
    radiation_debuff: bool = False
    last_action_tick: int = 0
    connected: bool = False
    creature_kills: int = 0
    online: bool = False

    def is_dead(self) -> bool:
        return self.health <= 0

    def can_act(self) -> bool:
        return self.status in (ActionStatus.IDLE, ActionStatus.MOVING)

    def view_range(self, day_phase: DayPhase, weather: Weather, terrain_bonus: int = 0) -> int:
        base = 2 + self.perception * 2 if day_phase in (DayPhase.NIGHT,) else 4 + self.perception * 2
        if weather == Weather.RADIATION_STORM:
            base -= 2
        base += terrain_bonus
        if self.equipment.main_hand == "searchlight" or self.equipment.off_hand == "searchlight":
            if day_phase == DayPhase.NIGHT:
                base += 4
        return max(1, base)

    def move_speed(self) -> int:
        return (self.agility + 1) // 2


@dataclass
class Structure:
    structure_id: str
    building_type: BuildingType
    position: Position
    hp: int; max_hp: int
    owner_id: str
    locked: bool = False
    open: bool = True

    @property
    def is_destroyed(self): return self.hp <= 0


@dataclass
class Creature:
    creature_id: str
    creature_type: str
    position: Position
    hp: int; max_hp: int
    attack: int; range: int; speed: int
    behavior: CreatureBehavior
    aggro_list: list[str] = field(default_factory=list)
    last_attacked_tick: int = 0
    spawn_tick: int = 0


@dataclass
class GroundItems:
    items: list[tuple[str, int]] = field(default_factory=list)
    dropped_tick: int = 0


@dataclass
class Tile:
    l1: Terrain = Terrain.FLAT
    l2_type: str = ""
    stone_amount: int = 0
    ore_type: str = ""
    ore_amount: int = 0
    ore_exposed: bool = False
    stone_depth: int = 0
    veg_type: str = ""
    veg_yield: int = 0
    structure: Optional[Structure] = None
    radiation: bool = False
    ground: Optional[GroundItems] = None
    regrow_timer: Optional[int] = None  # tick countdown for wood regrowth (P2)

    @property
    def passable(self) -> bool:
        if self.l1 in (Terrain.WATER, Terrain.TRENCH):
            return False
        # Stone blocks movement — must mine through it (cave-digging mechanic)
        if self.l2_type == 'stone' and self.stone_amount > 0:
            return False
        if self.structure and self.structure.building_type == BuildingType.WALL:
            return False
        if self.structure and self.structure.building_type == BuildingType.DOOR and not self.structure.open:
            return False
        return True

    @property
    def buildable(self) -> bool:
        if self.l1 in (Terrain.WATER, Terrain.TRENCH):
            return False
        if self.structure:
            return False
        return True

    @property
    def can_have_l2_stone(self) -> bool:
        """L2 Stone can exist on flat/sand, not on rock/water/trench"""
        return self.l1 in (Terrain.FLAT, Terrain.SAND)


@dataclass
class PowerNode:
    node_id: str
    position: Position
    capacity: int = 100
    stored: int = 100
    is_drop_pod: bool = False

    def consume(self, amount: int) -> bool:
        if self.stored >= amount:
            self.stored -= amount
            return True
        return False

    def recharge(self, amount: int):
        self.stored = min(self.capacity, self.stored + amount)


@dataclass
class WorldSnapshot:
    tick: int
    timestamp: float
    data: dict = field(default_factory=dict)


# ── Token Utilities ──────────────────────────────
def generate_token() -> str:
    return "et_" + secrets.token_hex(24)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def generate_agent_id(name: str) -> str:
    suffix = secrets.token_hex(2)[:4]
    clean = name.lower().replace(" ", "-")[:12]
    return f"{clean}-{suffix}"

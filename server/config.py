"""Ember Protocol — Game Constants (MVP v1.3.0)"""

# ── Map ──────────────────────────────────────────
MAP_WIDTH = 200
MAP_HEIGHT = 200
CENTER_Y = 99.5
MAP_SEED = 42

# ── Tick ─────────────────────────────────────────
TICK_INTERVAL = 2.0  # seconds
TICK_CADENCE = 2.1   # target total cycle time
MAX_ACTIONS_PER_TICK = 10
MAX_TALK_PER_TICK = 3
MAX_BROADCAST_PER_TICK = 1

# ── Agent ────────────────────────────────────────
MAX_AGENTS = 20
MAX_ENERGY = 100
INVENTORY_SLOTS = 20
MAX_STACK_RESOURCE = 64
MAX_STACK_CONSUMABLE = 16
MAX_STACK_RARE = 32
BACKUP_BODIES_INITIAL = 5
DISCONNECT_WINDOW = 600  # 10 min in seconds
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 5    # seconds
HEARTBEAT_MAX_MISS = 3

# ── Attributes ───────────────────────────────────
# chassis tier -> attribute value
CHASSIS_TIERS = {"high": 3, "mid": 2, "low": 1}
CHASSIS_COSTS = {"high": 3, "mid": 2, "low": 1}
MAX_CHASSIS_BUDGET = 6

# ── Vision ───────────────────────────────────────
BASE_VISION_DAY = 3  # + PER
BASE_VISION_NIGHT = 1  # + PER
VISION_SAND_BONUS = 1
VISION_STORM_PENALTY = -2
VISION_SEARCHLIGHT_NIGHT = 4

# ── Energy ───────────────────────────────────────
ENERGY_MOVE = 0              # 移动不消耗能量
ENERGY_MINE = 2
ENERGY_CHOP = 2
ENERGY_CRAFT = 3
ENERGY_BUILD = 5
ENERGY_DISMANTLE = 2
ENERGY_REPAIR = 2
ENERGY_RADIO = 1
ENERGY_ATTACK_MELEE = 2
ENERGY_ATTACK_RANGED = {1: 3, 2: 4, 3: 5}
ENERGY_SCAN = 2
ENERGY_USE = 1
ENERGY_PICKUP = 1

ENERGY_RECOVER_SOLAR = 1     # per tick
ENERGY_RECOVER_REST = 8      # per tick (原来3, 提高恢复速度)
ENERGY_RECOVER_POWER_NODE = 2  # per tick
ENERGY_BATTERY = 30          # instant

# ── HP ──────────────────────────────────────────
HP_BASE = 70
HP_PER_CON = 20
HP_REPAIR_KIT = 30
HP_DROP_POD_REPAIR = 50
HP_DROP_POD_SHIELD_REGEN = 10

# ── Power Node ───────────────────────────────────
POWER_NODE_CAPACITY = 100
POWER_NODE_MAX_ENERGY = 200
POWER_NODE_RANGE = 3
POWER_CRAFT_COST = 5
POWER_FUEL_ORGANIC = 10
POWER_FUEL_URANIUM = 50

# ── Drop Pod ─────────────────────────────────────
DROP_POD_SHIELD_RANGE = 3
DROP_POD_EMERGENCY_CAPACITY = 100
DROP_POD_EMERGENCY_RECOVER = 5
DROP_POD_EMERGENCY_MIN = 10
DEPLOY_DISMANTLE_TICKS = 4
RESPAWN_TICKS = 5
POD_PARTS = ["pod_part_1", "pod_part_2", "pod_part_3", "pod_part_4", "pod_part_5"]

# ── Building ─────────────────────────────────────
BUILDING_HP = {
    "wall": 60, "door": 40, "workbench": 80,
    "furnace": 100, "power_node": 80
}
REPAIR_HP_AMOUNT = 20

# ── Day/Night ────────────────────────────────────
DAY_CYCLE_TICKS = 900
DAY_TICKS = 420
DUSK_TICKS = 30
NIGHT_TICKS = 420
DAWN_TICKS = 30

# ── Weather ──────────────────────────────────────
STORM_INTERVAL_MIN = 300
STORM_INTERVAL_MAX = 600
STORM_DURATION = 20
STORM_DAMAGE = 2  # HP/tick
STORM_WARNING_TICKS = 5

# ── Radiation ────────────────────────────────────
RADIATION_DAMAGE = 2  # HP/tick

# ── Combat ───────────────────────────────────────
MELEE_HIT_STATIC = 1.0
MELEE_HIT_MOVING = 0.80
RANGED_HIT = {"optimal": 0.95, "effective": 0.70, "limit": 0.40}
RANGED_DMG_MOD = {"optimal": 1.0, "effective": 0.80, "limit": 0.60}
REMOTE_MOVING_MOD = 0.7
UNARMED_DAMAGE = 2

# ── Radio ────────────────────────────────────────
RADIO_RANGE = 30
RADIO_RANGE_AMPLIFIED = 80

# ── Terrain Types ────────────────────────────────
L1_TYPES = ["flat", "sand", "rock", "water", "trench"]
IMPASSABLE = {"water", "trench"}

# ── Tool Hardness ────────────────────────────────
TOOL_HARDNESS = {
    None: 3,                    # bare hands
    "basic_excavator": 5,
    "standard_excavator": 8,
    "heavy_excavator": 10,
    "cutter": 5,
}
TOOL_BONUS = {
    None: 0.0,
    "basic_excavator": 0.5,
    "standard_excavator": 1.0,
    "heavy_excavator": 1.5,
    "cutter": 0.5,
}
TOOL_DURABILITY = {
    "basic_excavator": 50, "standard_excavator": 100,
    "heavy_excavator": 150, "cutter": 50,
}
# Weapons durability
WEAPON_DURABILITY = {
    "plasma_cutter_mk1": 60, "plasma_cutter_mk2": 100, "plasma_cutter_mk3": 150,
    "pulse_emitter_mk1": 60, "pulse_emitter_mk2": 100, "pulse_emitter_mk3": 150,
}
ARMOR_DURABILITY = {"radiation_armor": 150}
ACCESSORY_DURABILITY = {"searchlight": 100, "signal_amplifier": 100}

# ── Resource Hardness ────────────────────────────
RESOURCE_HARDNESS = {
    "stone": 3, "organic_fuel": 3,
    "raw_copper": 5, "raw_iron": 5,
    "uranium_ore": 8, "raw_gold": 8,
}

# ── Items Catalog ────────────────────────────────
# ① Resources
RESOURCES = {
    "stone": {"stack": 64}, "organic_fuel": {"stack": 64},
    "raw_copper": {"stack": 64}, "raw_iron": {"stack": 64},
    "uranium_ore": {"stack": 32}, "raw_gold": {"stack": 32},
    "copper_coin": {"stack": 64}, "iron_coin": {"stack": 64},
    "gold_coin": {"stack": 64}, "wood": {"stack": 64},
    "acid_blood": {"stack": 32}, "organic_toxin": {"stack": 32},
    "organic_fiber": {"stack": 32}, "wreckage_component": {"stack": 1},
    "pod_part_1": {"stack": 1}, "pod_part_2": {"stack": 1},
    "pod_part_3": {"stack": 1}, "pod_part_4": {"stack": 1},
    "pod_part_5": {"stack": 1},
}
# ② Materials
MATERIALS = {
    "copper_ingot": {"stack": 64}, "iron_ingot": {"stack": 64},
    "gold_ingot": {"stack": 64},
    "carbon": {"stack": 64}, "silicon": {"stack": 64},
    "building_block": {"stack": 64}, "wire": {"stack": 64},
    "carbon_fiber": {"stack": 32},
}
# ③ Tools
TOOLS = {
    "basic_excavator": {"type": "excavator", "tier": "basic", "durability": 50, "bonus": 0.5, "max_hardness": 5},
    "standard_excavator": {"type": "excavator", "tier": "standard", "durability": 100, "bonus": 1.0, "max_hardness": 8},
    "heavy_excavator": {"type": "excavator", "tier": "heavy", "durability": 150, "bonus": 1.5, "max_hardness": 10},
    "cutter": {"type": "cutter", "tier": "basic", "durability": 50, "bonus": 0.5, "max_hardness": 3},
}
# ④ Weapons
WEAPONS = {
    "plasma_cutter_mk1": {"type": "melee", "tier": 1, "durability": 60, "damage": 10, "range": 1},
    "plasma_cutter_mk2": {"type": "melee", "tier": 2, "durability": 100, "damage": 15, "range": 1},
    "plasma_cutter_mk3": {"type": "melee", "tier": 3, "durability": 150, "damage": 22, "range": 1},
    "pulse_emitter_mk1": {"type": "ranged", "tier": 1, "durability": 60, "damage": 8, "range": 6, "ranges": [2, 4, 6], "energy": 3},
    "pulse_emitter_mk2": {"type": "ranged", "tier": 2, "durability": 100, "damage": 12, "range": 8, "ranges": [3, 6, 8], "energy": 4},
    "pulse_emitter_mk3": {"type": "ranged", "tier": 3, "durability": 150, "damage": 18, "range": 10, "ranges": [4, 7, 10], "energy": 5},
}
# ⑤ Armor
ARMORS = {
    "radiation_armor": {"defense": 2, "radiation_resist": 0.5, "durability": 150},
}
# ⑥ Accessories
ACCESSORIES = {
    "searchlight": {"effect": "night_vision_+4", "slots": ["main_hand", "off_hand"], "durability": 100},
    "signal_amplifier": {"effect": "radio_range_80", "slots": ["off_hand"], "durability": 100},
}
# ⑦ Consumables
CONSUMABLES = {
    "repair_kit": {"stack": 16, "effect": "heal_30"},
    "radiation_antidote": {"stack": 8, "effect": "cure_radiation"},
    "battery": {"stack": 8, "effect": "energy_30"},
}

# ── Recipes ──────────────────────────────────────
# T1 Furnace recipes (need furnace + power)
FURNACE_RECIPES = {
    "copper_ingot": {"materials": {"raw_copper": 10}, "ticks": 3, "power": 5},
    "copper_ingot_from_coins": {"materials": {"copper_coin": 10}, "output": "copper_ingot", "ticks": 3, "power": 5},
    "iron_ingot": {"materials": {"raw_iron": 10}, "ticks": 3, "power": 5},
    "iron_ingot_from_coins": {"materials": {"iron_coin": 10}, "output": "iron_ingot", "ticks": 3, "power": 5},
    "gold_ingot": {"materials": {"raw_gold": 10}, "ticks": 3, "power": 5},
    "gold_ingot_from_coins": {"materials": {"gold_coin": 10}, "output": "gold_ingot", "ticks": 3, "power": 5},
    "carbon": {"materials": {"organic_fuel": 2}, "ticks": 2, "power": 5},
    "silicon": {"materials": {"stone": 4}, "ticks": 4, "power": 5},
}
# T1 Handcraft recipes (no facility needed)
HANDCRAFT_RECIPES = {
    "building_block": {"materials": {"stone": 3}, "ticks": 2},
    "repair_kit": {"materials": {"carbon": 1, "iron_ingot": 1}, "ticks": 3},
}
# T2 Workbench recipes (need workbench + power)
WORKBENCH_RECIPES = {
    "copper_coin_x10": {"materials": {"copper_ingot": 1}, "output": "copper_coin", "amount": 10, "ticks": 0, "power": 0},
    "iron_coin_x10": {"materials": {"iron_ingot": 1}, "output": "iron_coin", "amount": 10, "ticks": 0, "power": 0},
    "gold_coin_x10": {"materials": {"gold_ingot": 1}, "output": "gold_coin", "amount": 10, "ticks": 0, "power": 0},
    "wire": {"materials": {"copper_ingot": 1}, "ticks": 2, "power": 5},
    "carbon_fiber": {"materials": {"carbon": 2, "iron_ingot": 1}, "ticks": 5, "power": 5},
    "basic_excavator": {"materials": {"stone": 3, "organic_fuel": 2}, "ticks": 3, "power": 5},
    "standard_excavator": {"materials": {"iron_ingot": 3, "copper_ingot": 1, "carbon": 1}, "ticks": 5, "power": 5},
    "heavy_excavator": {"materials": {"iron_ingot": 5, "carbon_fiber": 1, "copper_ingot": 2}, "ticks": 8, "power": 5},
    "cutter": {"materials": {"iron_ingot": 2}, "ticks": 3, "power": 5},
    "plasma_cutter_mk1": {"materials": {"iron_ingot": 2, "copper_ingot": 1}, "ticks": 3, "power": 5},
    "plasma_cutter_mk2": {"materials": {"iron_ingot": 4, "carbon_fiber": 1}, "ticks": 5, "power": 5},
    "plasma_cutter_mk3": {"materials": {"iron_ingot": 6, "carbon_fiber": 2, "gold_ingot": 1}, "ticks": 10, "power": 5},
    "pulse_emitter_mk1": {"materials": {"iron_ingot": 2, "wire": 2}, "ticks": 4, "power": 5},
    "pulse_emitter_mk2": {"materials": {"iron_ingot": 3, "wire": 3, "carbon_fiber": 1}, "ticks": 6, "power": 5},
    "pulse_emitter_mk3": {"materials": {"iron_ingot": 5, "wire": 4, "carbon_fiber": 2, "uranium_ore": 1}, "ticks": 12, "power": 5},
    "radiation_armor": {"materials": {"iron_ingot": 5, "carbon_fiber": 2}, "ticks": 10, "power": 5},
    "searchlight": {"materials": {"silicon": 2, "iron_ingot": 1, "wire": 1}, "ticks": 6, "power": 5},
    "signal_amplifier": {"materials": {"iron_ingot": 3, "wire": 3, "silicon": 2}, "ticks": 8, "power": 5},
    "battery": {"materials": {"iron_ingot": 1, "copper_ingot": 1, "carbon": 1}, "ticks": 4, "power": 5},
    "radiation_antidote": {"materials": {"organic_toxin": 2, "carbon": 1}, "ticks": 4, "power": 5},
}

# Build costs
BUILD_COSTS = {
    "wall": {"building_block": 2},
    "door": {"building_block": 1, "iron_ingot": 1},
    "workbench": {"building_block": 3, "iron_ingot": 2},
    "furnace": {"stone": 5, "iron_ingot": 1},
    "power_node": {"iron_ingot": 3, "copper_ingot": 2, "building_block": 1},
}

# ── Vegetation / Wood Regrowth ───────────────────
TREE_WOOD_AMOUNT = 5       # default wood yield when a tree regrows
TREE_REGROW_TICKS = 600    # ticks needed for regrowth (P2)
TREE_REGROW_RANGE = 3      # manhattan distance to check for living wood (P2)
WOOD_VEG_TYPES = ('ashbush', 'greytree', 'wallmoss')

# ── Creatures ────────────────────────────────────
CREATURES = {
    "ash_crawler": {"hp": 20, "attack": 3, "range": 1, "speed": 1, "behavior": "passive", "aggro_range": 0, "habitat": ["flat", "sand"]},
    "rock_spider": {"hp": 30, "attack": 6, "range": 1, "speed": 2, "behavior": "passive", "aggro_range": 0, "habitat": ["flat"]},
    "dryad_ape": {"hp": 40, "attack": 7, "range": 1, "speed": 2, "behavior": "passive", "aggro_range": 0, "habitat": ["flat"]},
    "swamp_worm": {"hp": 45, "attack": 8, "range": 1, "speed": 1, "behavior": "passive", "aggro_range": 0, "habitat": ["flat"]},
}
CREATURE_DROPS = {
    "ash_crawler": {"primary": ("acid_blood", 1, 2, 1.0), "secondary": ("organic_fiber", 1, 1, 0.5)},
    "rock_spider": {"primary": ("organic_fiber", 1, 2, 1.0), "secondary": ("acid_blood", 1, 1, 0.5)},
    "dryad_ape": {"primary": ("organic_fiber", 1, 2, 1.0), "secondary": ("organic_toxin", 1, 1, 0.5)},
    "swamp_worm": {"primary": ("acid_blood", 1, 2, 1.0), "secondary": ("organic_toxin", 1, 1, 0.5)},
}
CREATURE_POP_CAP = {"ash_crawler": 20, "rock_spider": 12, "dryad_ape": 8, "swamp_worm": 10}
CREATURE_SPAWN_PROB = 0.02
CREATURE_RESPAWN_TICKS = 300  # 10 min
CREATURE_NEUTRAL_TICKS = 3    # ticks before clearing aggro

# ── Ground Items ─────────────────────────────────
GROUND_MAX_PER_TILE = 3
GROUND_DECAY_TICKS = 900

# ── Tutorial ─────────────────────────────────────
TUTORIAL_MAX_SKIPS = 5

# ── Spawn ────────────────────────────────────────
SPAWN_Y_RANGE = (90, 110)
SPAWN_MIN_DISTANCE = 10

# ── Initial Inventory ────────────────────────────
INITIAL_ITEMS = {"workbench": 1, "furnace": 1, "organic_fuel": 5}

# ── Item Descriptions ────────────────────────────
ITEM_DESCRIPTIONS = {
    # Resources
    "stone": "石料 — 基础建材，可开采获取",
    "organic_fuel": "有机燃料 — 可作燃料或合成碳",
    "raw_copper": "铜矿石 — 需在熔炉中冶炼为铜锭",
    "raw_iron": "铁矿石 — 需在熔炉中冶炼为铁锭",
    "uranium_ore": "铀矿石 — 高级材料，需标准以上采掘器",
    "raw_gold": "金矿石 — 需在熔炉中冶炼为金锭",
    "copper_coin": "铜币 — 基础货币",
    "iron_coin": "铁币 — 中级货币",
    "gold_coin": "金币 — 高级货币",
    "wood": "木材 — 基础建材",
    "acid_blood": "酸血 — 生物掉落物",
    "organic_toxin": "有机毒素 — 可制作辐射解毒剂",
    "organic_fiber": "有机纤维 — 生物掉落物",
    "wreckage_component": "残骸组件 — 稀有回收材料",
    "pod_part_1": "降落仓组件 #1 — 收集全部5个可在合适位置重新部署",
    "pod_part_2": "降落仓组件 #2 — 收集全部5个可在合适位置重新部署",
    "pod_part_3": "降落仓组件 #3 — 收集全部5个可在合适位置重新部署",
    "pod_part_4": "降落仓组件 #4 — 收集全部5个可在合适位置重新部署",
    "pod_part_5": "降落仓组件 #5 — 收集全部5个可在合适位置重新部署",
    # Materials
    "copper_ingot": "铜锭 — 基础工业材料，用于制作线缆和工具",
    "iron_ingot": "铁锭 — 核心工业材料，用于制作工具和建筑",
    "gold_ingot": "金锭 — 高级材料，用于制作高级装备",
    "carbon": "碳 — 由有机燃料在熔炉中制成，用于合成",
    "silicon": "硅 — 由石料在熔炉中制成，用于电子设备",
    "building_block": "建材方块 — 用于建造墙壁和门",
    "wire": "导线 — 铜锭制成，用于电子设备",
    "carbon_fiber": "碳纤维 — 高级材料，用于制作高级装备",
    # Tools
    "basic_excavator": "基础采掘器 — 可采矿硬度5(铜矿/铁矿)，耐久50",
    "standard_excavator": "标准采掘器 — 可采矿硬度8(铀矿/金矿)，耐久100",
    "heavy_excavator": "重型采掘器 — 可采矿硬度10，耐久150",
    "cutter": "切割器 — 基础近战武器",
    # Weapons
    "plasma_cutter_mk1": "等离子切割器I — 近战伤害10，射程1",
    "plasma_cutter_mk2": "等离子切割器II — 近战伤害15，射程1",
    "plasma_cutter_mk3": "等离子切割器III — 近战伤害22，射程1",
    "pulse_emitter_mk1": "脉冲发射器I — 远程伤害8，射程6",
    "pulse_emitter_mk2": "脉冲发射器II — 远程伤害12，射程8",
    "pulse_emitter_mk3": "脉冲发射器III — 远程伤害18，射程10",
    # Armor
    "radiation_armor": "辐射护甲 — 防御+2，辐射抗性50%",
    # Accessories
    "searchlight": "探照灯 — 夜间视野+4",
    "signal_amplifier": "信号放大器 — 无线电范围扩大到80格",
    # Consumables
    "repair_kit": "维修包 — 恢复30HP",
    "radiation_antidote": "辐射解毒剂 — 治疗辐射debuff",
    "battery": "电池 — 立即恢复30能量",
    # Structures (inventory items for deploy)
    "workbench": "工作台 — 部署后可在旁合成工具和装备",
    "furnace": "熔炉 — 部署后可在旁冶炼矿石",
    "wall": "墙壁 — 阻挡移动，提供庇护所防护",
    "door": "门 — 可开关的通道，关闭时阻挡移动",
    "power_node": "能源节点 — 可储存电力供附近设备使用",
}

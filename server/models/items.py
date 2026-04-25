"""Ember Protocol — Item Definitions Database
All items from PRD v0.9.1
"""

from server.models import ItemDef, ItemCategory, EquipmentSlot

# ─── Item Database ────────────────────────────────────────────────────

ITEM_DB: dict[str, ItemDef] = {}


def _reg(item: ItemDef):
    ITEM_DB[item.id] = item
    return item


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ① Resources (Raw Gathered Materials)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="stone", name="Stone", name_zh="石头", category=ItemCategory.RESOURCE,
             stack_max=64, rarity="common", source="mine_vein", gather_action="mine",
             gather_hardness=3))

_reg(ItemDef(id="organic_fuel", name="Organic Fuel", name_zh="有机燃料", category=ItemCategory.RESOURCE,
             stack_max=64, rarity="common", source="mine_vein", gather_action="mine",
             gather_hardness=3))

_reg(ItemDef(id="raw_copper", name="Raw Copper", name_zh="铜矿", category=ItemCategory.RESOURCE,
             stack_max=64, rarity="uncommon", source="mine_vein", gather_action="mine",
             gather_hardness=5, min_tool="basic_excavator"))

_reg(ItemDef(id="raw_iron", name="Raw Iron", name_zh="铁矿", category=ItemCategory.RESOURCE,
             stack_max=64, rarity="uncommon", source="mine_vein", gather_action="mine",
             gather_hardness=5, min_tool="basic_excavator"))

_reg(ItemDef(id="uranium_ore", name="Uranium Ore", name_zh="铀矿", category=ItemCategory.RESOURCE,
             stack_max=32, rarity="rare", source="mine_vein", gather_action="mine",
             gather_hardness=8, min_tool="heavy_excavator"))

_reg(ItemDef(id="raw_gold", name="Raw Gold", name_zh="金矿", category=ItemCategory.RESOURCE,
             stack_max=32, rarity="legendary", source="mine_vein", gather_action="mine",
             gather_hardness=8, min_tool="heavy_excavator"))

_reg(ItemDef(id="wood", name="Wood", name_zh="木材", category=ItemCategory.RESOURCE,
             stack_max=64, rarity="common", source="vegetation", gather_action="chop"))

_reg(ItemDef(id="acid_blood", name="Acid Blood", name_zh="酸血", category=ItemCategory.RESOURCE,
             stack_max=32, rarity="uncommon", source="creature_drop"))

_reg(ItemDef(id="bio_fuel", name="Bio Fuel", name_zh="生物燃料", category=ItemCategory.RESOURCE,
             stack_max=32, rarity="uncommon", source="creature_drop"))

_reg(ItemDef(id="organic_toxin", name="Organic Toxin", name_zh="有机毒素", category=ItemCategory.RESOURCE,
             stack_max=32, rarity="uncommon", source="creature_drop"))

_reg(ItemDef(id="bio_bone", name="Bio Bone", name_zh="生物骨", category=ItemCategory.RESOURCE,
             stack_max=32, rarity="uncommon", source="creature_drop"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ①.5 Currency (Ingot ↔ Coin)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="ember_coin", name="Ember Coin", name_zh="余烬币", category=ItemCategory.MATERIAL,
             stack_max=999, tier=0))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ② Materials (Processed Semi-Finished)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="copper_ingot", name="Copper Ingot", name_zh="铜碇", category=ItemCategory.MATERIAL,
             stack_max=64, tier=1, craft_station="furnace"))

_reg(ItemDef(id="iron_ingot", name="Iron Ingot", name_zh="铁碇", category=ItemCategory.MATERIAL,
             stack_max=64, tier=1, craft_station="furnace"))

_reg(ItemDef(id="uranium_ingot", name="Uranium Ingot", name_zh="铀碇", category=ItemCategory.MATERIAL,
             stack_max=32, tier=3, craft_station="furnace"))

_reg(ItemDef(id="gold_ingot", name="Gold Ingot", name_zh="金碇", category=ItemCategory.MATERIAL,
             stack_max=32, tier=3, craft_station="furnace"))

_reg(ItemDef(id="carbon", name="Carbon", name_zh="碳", category=ItemCategory.MATERIAL,
             stack_max=64, tier=1, craft_station="furnace"))

_reg(ItemDef(id="silicon", name="Silicon", name_zh="硅", category=ItemCategory.MATERIAL,
             stack_max=64, tier=1, craft_station="furnace"))

_reg(ItemDef(id="building_block", name="Building Block", name_zh="建筑方块", category=ItemCategory.MATERIAL,
             stack_max=64, tier=1, craft_station="hand"))

_reg(ItemDef(id="wire", name="Wire", name_zh="导线", category=ItemCategory.MATERIAL,
             stack_max=64, tier=2, craft_station="workbench"))

_reg(ItemDef(id="carbon_fiber", name="Carbon Fiber", name_zh="碳纤维", category=ItemCategory.MATERIAL,
             stack_max=32, tier=2, craft_station="workbench"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ③ Tools
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="basic_excavator", name="Basic Excavator", name_zh="基础采掘器",
             category=ItemCategory.TOOL, stack_max=1, durability_max=50,
             equip_slot=EquipmentSlot.MAIN_HAND,
             tool_type="excavator", tool_tier="basic",
             bonus_type="mining", bonus_value=0.5, max_hardness=5))

_reg(ItemDef(id="standard_excavator", name="Standard Excavator", name_zh="标准采掘器",
             category=ItemCategory.TOOL, stack_max=1, durability_max=100,
             equip_slot=EquipmentSlot.MAIN_HAND,
             tool_type="excavator", tool_tier="standard",
             bonus_type="mining", bonus_value=1.0, max_hardness=8))

_reg(ItemDef(id="heavy_excavator", name="Heavy Excavator", name_zh="重型采掘器",
             category=ItemCategory.TOOL, stack_max=1, durability_max=150,
             equip_slot=EquipmentSlot.MAIN_HAND,
             tool_type="excavator", tool_tier="heavy",
             bonus_type="mining", bonus_value=1.5, max_hardness=10))

_reg(ItemDef(id="cutter", name="Cutter", name_zh="切割器",
             category=ItemCategory.TOOL, stack_max=1, durability_max=50,
             equip_slot=EquipmentSlot.MAIN_HAND,
             tool_type="cutter", tool_tier="basic",
             bonus_type="chopping", bonus_value=0.5, max_hardness=0))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ④ Weapons — Melee (Plasma Cutter)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="plasma_cutter_mk1", name="Plasma Cutter Mk.I", name_zh="等离子切割刀 Mk.I",
             category=ItemCategory.WEAPON, stack_max=1, durability_max=60,
             equip_slot=EquipmentSlot.MAIN_HAND,
             weapon_type="melee", weapon_tier="basic",
             damage=10, attack_range=1, optimal_range=1, energy_cost_attack=2))

_reg(ItemDef(id="plasma_cutter_mk2", name="Plasma Cutter Mk.II", name_zh="等离子切割刀 Mk.II",
             category=ItemCategory.WEAPON, stack_max=1, durability_max=100,
             equip_slot=EquipmentSlot.MAIN_HAND,
             weapon_type="melee", weapon_tier="standard",
             damage=15, attack_range=1, optimal_range=1, energy_cost_attack=2))

_reg(ItemDef(id="plasma_cutter_mk3", name="Plasma Cutter Mk.III", name_zh="等离子切割刀 Mk.III",
             category=ItemCategory.WEAPON, stack_max=1, durability_max=150,
             equip_slot=EquipmentSlot.MAIN_HAND,
             weapon_type="melee", weapon_tier="heavy",
             damage=22, attack_range=1, optimal_range=1, energy_cost_attack=2))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ④ Weapons — Ranged (Pulse Emitter)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="pulse_emitter_mk1", name="Pulse Emitter Mk.I", name_zh="脉冲发射器 Mk.I",
             category=ItemCategory.WEAPON, stack_max=1, durability_max=60,
             equip_slot=EquipmentSlot.MAIN_HAND,
             weapon_type="ranged", weapon_tier="basic",
             damage=8, attack_range=6, optimal_range=2, energy_cost_attack=3))

_reg(ItemDef(id="pulse_emitter_mk2", name="Pulse Emitter Mk.II", name_zh="脉冲发射器 Mk.II",
             category=ItemCategory.WEAPON, stack_max=1, durability_max=100,
             equip_slot=EquipmentSlot.MAIN_HAND,
             weapon_type="ranged", weapon_tier="standard",
             damage=12, attack_range=8, optimal_range=3, energy_cost_attack=4))

_reg(ItemDef(id="pulse_emitter_mk3", name="Pulse Emitter Mk.III", name_zh="脉冲发射器 Mk.III",
             category=ItemCategory.WEAPON, stack_max=1, durability_max=150,
             equip_slot=EquipmentSlot.MAIN_HAND,
             weapon_type="ranged", weapon_tier="heavy",
             damage=18, attack_range=10, optimal_range=4, energy_cost_attack=5))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑤ Armor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="radiation_armor", name="Radiation Suit", name_zh="辐射防护服",
             category=ItemCategory.ARMOR, stack_max=1, durability_max=150,
             equip_slot=EquipmentSlot.ARMOR,
             defense=2, resistance_type="radiation", resistance_value=0.5))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑥ Accessories
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="searchlight", name="Searchlight", name_zh="探照灯",
             category=ItemCategory.ACCESSORY, stack_max=1, durability_max=200,
             equip_slot=EquipmentSlot.MAIN_HAND,
             effect_type="vision_boost", effect_value=4))

_reg(ItemDef(id="signal_amplifier", name="Signal Amplifier", name_zh="信号放大器",
             category=ItemCategory.ACCESSORY, stack_max=1, durability_max=200,
             equip_slot=EquipmentSlot.OFF_HAND,
             effect_type="comm_range", effect_value=80))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑦ Consumables
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="repair_kit", name="Simple Repair Kit", name_zh="简易修复包",
             category=ItemCategory.CONSUMABLE, stack_max=16,
             consumable_effect="heal", consumable_value=30, use_energy_cost=1))

_reg(ItemDef(id="radiation_antidote", name="Radiation Antidote", name_zh="辐射解药",
             category=ItemCategory.CONSUMABLE, stack_max=8,
             consumable_effect="cure_radiation", consumable_value=0, use_energy_cost=1))

_reg(ItemDef(id="battery", name="Battery", name_zh="电池",
             category=ItemCategory.CONSUMABLE, stack_max=8,
             consumable_effect="restore_energy", consumable_value=30, use_energy_cost=0))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Buildings (as deployable items)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_reg(ItemDef(id="solar_panel", name="Solar Panel", name_zh="太阳能板",
             category=ItemCategory.MATERIAL, stack_max=16, tier=2, craft_station="workbench"))


def get_item(item_id: str) -> ItemDef | None:
    return ITEM_DB.get(item_id)


def get_all_items() -> dict[str, ItemDef]:
    return dict(ITEM_DB)

# 📊 数据参考

## 物品表

### ① 资源（Raw Gathered Materials）

| ID | 名称 | 堆叠 | 稀有度 | 采集方式 | 硬度 | 最低工具 |
|----|------|------|--------|----------|------|----------|
| stone | 石头 | 64 | common | mine | **0** | 无(空手可采) |
| organic_fuel | 有机燃料 | 64 | common | mine | **0** | 无(空手可采) |
| raw_copper | 铜矿 | 64 | uncommon | mine | 5 | basic_excavator |
| raw_iron | 铁矿 | 64 | uncommon | mine | 5 | basic_excavator |
| uranium_ore | 铀矿 | 32 | rare | mine | 8 | heavy_excavator |
| raw_gold | 金矿 | 32 | legendary | mine | 8 | heavy_excavator |
| wood | 木材 | 64 | common | chop | 0 | 无 |
| acid_blood | 酸血 | 32 | uncommon | 生物掉落 | - | - |
| bio_fuel | 生物燃料 | 32 | uncommon | 生物掉落 | - | - |
| organic_toxin | 有机毒素 | 32 | uncommon | 生物掉落 | - | - |
| bio_bone | 生物骨 | 32 | uncommon | 生物掉落 | - | - |

### ② 货币

| ID | 名称 | 堆叠 |
|----|------|------|
| ember_coin | 余烬币 | 999 |

### ③ 材料（Processed Semi-Finished）

| ID | 名称 | 堆叠 | 等级 | 合成站 |
|----|------|------|------|--------|
| copper_ingot | 铜碇 | 64 | T1 | furnace |
| iron_ingot | 铁碇 | 64 | T1 | furnace |
| uranium_ingot | 铀碇 | 32 | T3 | furnace |
| gold_ingot | 金碇 | 32 | T3 | furnace |
| carbon | 碳 | 64 | T1 | furnace |
| silicon | 硅 | 64 | T1 | furnace |
| building_block | 建筑方块 | 64 | T1 | hand |
| wire | 导线 | 64 | T2 | workbench |
| carbon_fiber | 碳纤维 | 32 | T2 | workbench |
| solar_panel | 太阳能板 | 16 | T2 | workbench |

### ④ 工具

| ID | 名称 | 耐久 | 槽位 | 采矿加成 | 最大硬度 |
|----|------|------|------|----------|----------|
| basic_excavator | 基础采掘器 | 50 | main_hand | +50% | 5 |
| standard_excavator | 标准采掘器 | 100 | main_hand | +100% | 8 |
| heavy_excavator | 重型采掘器 | 150 | main_hand | +150% | 10 |
| cutter | 切割器 | 50 | main_hand | +50%(伐木) | 0 |

### ⑤ 武器

**近战（等离子切割刀）**

| ID | 名称 | 耐久 | 伤害 | 范围 | 能量消耗 |
|----|------|------|------|------|----------|
| plasma_cutter_mk1 | Mk.I | 60 | 10 | 1 | 2 |
| plasma_cutter_mk2 | Mk.II | 100 | 15 | 1 | 2 |
| plasma_cutter_mk3 | Mk.III | 150 | 22 | 1 | 2 |

**远程（脉冲发射器）**

| ID | 名称 | 耐久 | 伤害 | 范围 | 最优范围 | 能量消耗 |
|----|------|------|------|------|----------|----------|
| pulse_emitter_mk1 | Mk.I | 60 | 8 | 6 | 2 | 3 |
| pulse_emitter_mk2 | Mk.II | 100 | 12 | 8 | 3 | 4 |
| pulse_emitter_mk3 | Mk.III | 150 | 18 | 10 | 4 | 5 |

### ⑥ 护甲

| ID | 名称 | 耐久 | 槽位 | 物理防御 | 抗性 |
|----|------|------|------|----------|------|
| radiation_armor | 辐射防护服 | 150 | armor | -2 | 辐射-50% |

### ⑦ 配件

| ID | 名称 | 耐久 | 槽位 | 效果 |
|----|------|------|------|------|
| searchlight | 探照灯 | 200 | main_hand | 夜间视野+4 |
| signal_amplifier | 信号放大器 | 200 | off_hand | 通信范围30→80格 |

### ⑧ 消耗品

| ID | 名称 | 堆叠 | 效果 | 值 | 能量消耗 |
|----|------|------|------|-----|----------|
| repair_kit | 简易修复包 | 16 | 治疗HP | +30 | 1 |
| radiation_antidote | 辐射解药 | 8 | 消除辐射 | - | 1 |
| battery | 电池 | 8 | 恢复能量 | +30 | 0 |

---

## 配方表

### T1 手工配方（无需设施）

| ID | 产出 | 输入 | 耗时 |
|----|------|------|------|
| building_block | 建筑方块×1 | 石头×3 | 2 tick |
| repair_kit | 修复包×1 | 碳×1 + 铁碇×1 | 3 tick |

### 碇⇄币转换（手工）

| ID | 产出 | 输入 | 等级 |
|----|------|------|------|
| copper_ingot_to_coins | 余烬币×5 | 铜碇×1 | T1 |
| iron_ingot_to_coins | 余烬币×5 | 铁碇×1 | T1 |
| uranium_ingot_to_coins | 余烬币×20 | 铀碇×1 | T3 |
| gold_ingot_to_coins | 余烬币×50 | 金碇×1 | T3 |
| coins_to_copper_ingot | 铜碇×1 | 余烬币×5 | T1 |
| coins_to_iron_ingot | 铁碇×1 | 余烬币×5 | T1 |

### T1 冶炼配方（需要 furnace + 能源节点）

| ID | 产出 | 输入 | 耗时 | 电力 |
|----|------|------|------|------|
| copper_ingot | 铜碇×1 | 铜矿×2 | 3 | 5 |
| iron_ingot | 铁碇×1 | 铁矿×3 | 3 | 5 |
| uranium_ingot | 铀碇×1 | 铀矿×4 | 6 | 10 |
| gold_ingot | 金碇×1 | 金矿×4 | 6 | 10 |
| carbon | 碳×1 | 有机燃料×2 | 2 | 5 |
| silicon | 硅×1 | 石头×4 | 4 | 5 |

### T2 加工配方（需要 workbench + 能源节点）

| ID | 产出 | 输入 | 耗时 | 电力 |
|----|------|------|------|------|
| wire | 导线×1 | 铜碇×1 | 2 | 5 |
| carbon_fiber | 碳纤维×1 | 碳×2 + 铁碇×1 | 5 | 5 |

### T2 工具（workbench）

| ID | 产出 | 输入 | 耗时 | 电力 |
|----|------|------|------|------|
| basic_excavator | 基础采掘器×1 | 石头×3 + 有机燃料×2 | 3 | 5 |
| standard_excavator | 标准采掘器×1 | 铁碇×3 + 铜碇×1 + 碳×1 | 5 | 5 |
| heavy_excavator | 重型采掘器×1 | 铁碇×5 + 碳纤维×1 + 铜碇×2 | 8 | 5 |
| cutter | 切割器×1 | 铁碇×2 | 3 | 5 |

### T2 武器（workbench）

| ID | 产出 | 输入 | 耗时 | 电力 |
|----|------|------|------|------|
| plasma_cutter_mk1 | 等离子切割刀Mk.I×1 | 铁碇×2 + 铜碇×1 | 3 | 5 |
| plasma_cutter_mk2 | 等离子切割刀Mk.II×1 | 铁碇×4 + 碳纤维×1 | 5 | 5 |
| plasma_cutter_mk3 | 等离子切割刀Mk.III×1 | 铁碇×6 + 碳纤维×2 + 金碇×1 | 10 | 5 |
| pulse_emitter_mk1 | 脉冲发射器Mk.I×1 | 铁碇×2 + 导线×2 | 4 | 5 |
| pulse_emitter_mk2 | 脉冲发射器Mk.II×1 | 铁碇×3 + 导线×3 + 碳纤维×1 | 6 | 5 |
| pulse_emitter_mk3 | 脉冲发射器Mk.III×1 | 铁碇×5 + 导线×4 + 碳纤维×2 + 铀碇×1 | 12 | 5 |

### T2 装备 & 配件（workbench）

| ID | 产出 | 输入 | 耗时 | 电力 |
|----|------|------|------|------|
| radiation_armor | 辐射防护服×1 | 铁碇×5 + 碳纤维×2 | 10 | 5 |
| searchlight | 探照灯×1 | 硅×2 + 铁碇×1 + 导线×1 | 6 | 5 |
| signal_amplifier | 信号放大器×1 | 铁碇×3 + 导线×3 + 硅×2 | 8 | 5 |
| solar_panel | 太阳能板×1 | 硅×2 + 碳纤维×1 + 导线×1 | 8 | 5 |
| battery | 电池×1 | 铁碇×1 + 铜碇×1 + 碳×1 | 4 | 5 |
| radiation_antidote | 辐射解药×1 | 有机毒素×2 + 碳×1 | 4 | 5 |

---

## 建筑数据

### 建造造价

| 建筑 | 造价 | HP |
|------|------|-----|
| wall | building_block×2 | 60 |
| door | building_block×1 + iron_ingot×1 | 40 |
| workbench | building_block×3 + iron_ingot×2 | 80 |
| furnace | stone×5 + iron_ingot×1 | 100 |
| storage | building_block×2 + iron_ingot×1 | 50 |
| solar_array | solar_panel×3 + building_block×2 | 60 |
| power_node | iron_ingot×3 + copper_ingot×2 + building_block×1 | 80 |

### 拆解回收（50%材料）

| 建筑 | 回收材料 |
|------|----------|
| wall | building_block×1 |
| door | building_block×1 |
| workbench | building_block×1 + iron_ingot×1 |
| furnace | stone×2 + iron_ingot×1 |
| storage | building_block×1 |
| solar_array | solar_panel×1 + building_block×1 |
| power_node | iron_ingot×1 + copper_ingot×1 |
| drop_pod | iron_ingot×2 + building_block×2 + copper_ingot×1 |

### 能源节点

- 容量：100 能量
- 供电范围：3 格（曼哈顿距离）
- 太阳能充电：5 能量/tick（平均分配给范围内所有能源节点）
- 围合空间内设施通过能源节点获得电力

---

## 地图覆盖物

### 矿物

| 覆盖物ID | 产出物品 | 可出现地形 |
|----------|----------|------------|
| ore_stone | stone | FLAT, ROCK, TRENCH, HIGHLAND |
| ore_organic | organic_fuel | FLAT, ROCK, TRENCH, HIGHLAND |
| ore_copper | raw_copper | ROCK, TRENCH, HIGHLAND |
| ore_iron | raw_iron | ROCK, TRENCH, HIGHLAND |
| ore_uranium | uranium_ore | ROCK, HIGHLAND |
| ore_gold | raw_gold | ROCK, HIGHLAND |

### 植被

| 覆盖物ID | 产出物品 | 可出现地形 |
|----------|----------|------------|
| veg_ashbrush | wood | FLAT, SAND, HIGHLAND |
| veg_greytree | wood | FLAT, ROCK, HIGHLAND |
| veg_wallmoss | wood | TRENCH, ROCK |

---

## 视野计算

```
基础视野 = 3 + PER (白天)
夜间视野 = max(1, 基础视野 - 2)
黄昏 = 基础视野 - 1
高地加成 = +2 (白天) / +1 (夜间)
探照灯 = +4 (夜间/黄昏/黎明)
辐射风暴 = -2
围合空间 = 可见整个围合区域
```

## 常量

| 常量 | 值 | 说明 |
|------|-----|------|
| TICK_INTERVAL | 2s | tick间隔 |
| DAY_CYCLE | 900 tick | 完整昼夜周期 |
| MAX_INVENTORY | 20 slots | 背包上限 |
| MAX_GROUND_ITEMS | 10 piles/tile | 地面物品上限 |
| ENCLOSURE_MAX | 64 tiles | 围合面积上限 |
| POWER_NODE_CAPACITY | 100 | 能源节点容量 |
| POWER_SUPPLY_RANGE | 3 | 能源供电范围 |
| SOLAR_CHARGE_RATE | 5/tick | 太阳能充电速率 |
| REST_CHARGE | 3/tick | 休息恢复 |
| WIRELESS_CHARGE | 2/tick | 节点充电加成 |
| BUILTIN_SOLAR | 1/tick | 内置太阳能 |
| BACKUP_BODIES | 5 | 重生次数 |
| POD_SHIELD_RANGE | 3 | 降落仓护盾范围 |
| HEARTBEAT_TIMEOUT | 60 tick (2min) | 心跳超时 |
| AUTO_LOGOUT | 300 tick (10min) | 自动下线 |

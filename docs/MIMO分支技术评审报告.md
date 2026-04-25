# Ember Protocol MIMO 分支技术评审报告

> **评审日期**: 2026-04-25
> **评审对象**: GitHub 分支 `Saviorzyy/Ember-Protocol/MIMO`
> **提交**: `007029b` — "feat: Ember Protocol MVP backend + frontend + tests"
> **评审标准**: PRD v0.9.1 技术可行性、代码质量、架构合理性、与 PRD 一致性

---

## 一、项目概览

### 1.1 交付内容

| 组件 | 文件 | 说明 |
|------|------|------|
| 后端 API | `server/api/main.py` | FastAPI 应用，REST + SSE 端点 |
| 游戏引擎 | `server/engine/game.py` | Tick 循环 + 行动结算 |
| 世界引擎 | `server/engine/world.py` | 地图生成 + 昼夜/天气 |
| 战斗系统 | `server/engine/combat.py` | 命中/伤害/采集公式 |
| 数据模型 | `server/models/__init__.py` | Agent/Tile/Item 等核心模型 |
| 物品数据库 | `server/models/items.py` | 全部物品定义 |
| 配方数据库 | `server/models/recipes.py` | 合成配方 |
| 测试套件 | `server/tests/test_core.py` | pytest 测试 |
| 观察界面 | `web/index.html` | Canvas 像素风格地图 |
| 注册页面 | `web/register.html` | 角色创建页面 |
| 快照渲染 | `tools/render_snapshots.py` | 地图可视化工具 |

### 1.2 技术栈

- **后端**: Python 3.12 + FastAPI + Pydantic v2 + httpx
- **前端**: 纯 HTML/CSS/JS (单文件)，Canvas 2D 渲染
- **测试**: pytest
- **地图生成**: 自定义简化柏林噪声 (MD5 hash-based)

---

## 二、总体评价

**这是一个功能完整的 MVP Demo，核心循环已跑通，但存在大量与 PRD 不一致、架构隐患和代码质量问题。不建议在此基础上直接迭代，建议作为参考实现提取有价值部分后重新设计。**

| 维度 | 评分 | 说明 |
|------|------|------|
| PRD 一致性 | ⭐⭐☆☆☆ | 大量数值/机制与 PRD 不符 |
| 架构设计 | ⭐⭐⭐☆☆ | 分层清晰但存在关键设计缺陷 |
| 代码质量 | ⭐⭐☆☆☆ | 类型安全、并发处理、边界条件多处问题 |
| 可测试性 | ⭐⭐⭐☆☆ | 有测试覆盖但不够全面 |
| 可扩展性 | ⭐⭐☆☆☆ | 单进程、全内存状态，无法水平扩展 |
| 文档 | ⭐⭐⭐☆☆ | 代码注释充分但缺少架构文档 |

---

## 三、🔴 严重问题 (P0)

### P0-1: 地图尺寸与 PRD 严重不符

| 项目 | PRD 要求 | 实际代码 | 影响 |
|------|---------|---------|------|
| 地图尺寸 | 400×400 | **100×100** | 仅为 PRD 的 6.25%，无法验证区域渐进设计 |
| 出生区域 | Y=180~220 | Y=40~60 (按比例) | 区域划分算法比例正确但绝对尺寸太小 |

**位置**: `server/api/main.py:35`, `server/config/settings.py:4-5`

```python
engine = GameEngine(map_width=100, map_height=100, seed=42)  # 应为 400×400
```

**建议**: 至少改为 400×400 验证性能，或提供配置化参数。

---

### P0-2: 配方与 PRD 严重不符 — 经济系统崩溃

**核心问题**: 配方使用了错误的材料名称和数量，导致经济循环不成立。

| 配方 | PRD 要求 | 实际代码 | 问题 |
|------|---------|---------|------|
| 铜碇 | 未提炼铜矿×10 | **raw_copper×2** | 数量错误，产出应为"碇"而非"板" |
| 铁碇 | 未提炼铁矿×10 | **raw_iron×3** | 同上 |
| 基础采掘器 | 石料×3 + 有机燃料×2 (PRD v0.9.1 修复后) | **stone×3 + organic_fuel×2** | ✅ 正确 |
| 标准采掘器 | 铁碇×3 + 铜碇×1 + 碳×1 | **iron_slab×3 + copper_slab×1 + carbon×1** | 材料名错误（应为"碇"ingot，不是"板"slab） |
| 等离子切割刀 Mk.III | 铁碇×6 + 碳纤维×2 + **金碇×1** | **iron_slab×6 + carbon_fiber×2 + raw_gold×1** | 使用原始金矿石而非金碇 |
| 脉冲发射器 Mk.III | 铁碇×5 + 电线×4 + 碳纤维×2 + **铀矿×1** | 同上 | 铀矿不应直接用于武器合成 |

**位置**: `server/models/recipes.py`

**更严重的问题**: PRD 的"碇⇄币"双向转换体系**完全未实现**。没有铜币/铁币/金币的定义和转换配方。

**位置**: `server/models/items.py` — 缺少 `copper_coin`, `iron_coin`, `gold_coin`

---

### P0-3: 物品数据库术语与 PRD 不一致

| PRD 术语 | 代码中的 ID | 问题 |
|---------|-----------|------|
| 铜碇 (copper_ingot) | `copper_slab` | 完全错误的命名 |
| 铁碇 (iron_ingot) | `iron_slab` | 完全错误的命名 |
| 金碇 (gold_ingot) | **不存在** | 未定义 |
| 建材方块 | `building_block` | ✅ 正确 |
| 太阳板 | `solar_panel` | ✅ 正确 |

**影响**: 所有配方、物品引用、API 返回都使用了错误的术语，与 PRD 文档完全对不上。

---

### P0-4: 能源节点储电机制错误

**PRD 要求**: 能源节点有独立的 `stored_power` 字段，容量 100，给设施/角色供电。

**实际代码**: 用 `Building.hp` 来代理储电量！

```python
# server/engine/game.py:393
if not power_node or power_node.hp < recipe.power_cost:  # hp 当作储电！
    return ActionResult(..., detail="Power node has insufficient power")

# server/engine/game.py:421-423
if power_node:
    power_node.hp -= recipe.power_cost  # 扣 hp 当作耗电！
```

**位置**: `server/engine/game.py:393`, `421-423`, `server/engine/game.py:1109-1110`（太阳能充电也充到 hp）

**影响**: 建筑 HP 和储电量混淆，建筑受损 = 没电，完全错误。

---

### P0-5: Tick 循环未实际驱动 Agent 通信

**PRD 要求**: 服务器每 tick 向 Agent POST 状态，Agent 返回行动，tick 结束统一结算。

**实际代码**: `tick_loop()` 只调用 `engine.tick()`，**完全没有向 Agent 推送状态**！

```python
# server/api/main.py:60-71
async def tick_loop():
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        if engine:
            result = engine.tick()  # 只推进世界，不推 Agent
            # In full implementation, push state to agents here
```

**位置**: `server/api/main.py:60-71`

**影响**: Agent 完全不会被调用，游戏只是空转。`resolve_tick()` 方法有 `tasks.push()` 这种**不存在的 API 调用**（应该是 `tasks.append()` + `asyncio.gather`）。

```python
# server/engine/game.py:147-153
tasks = []
for agent_id, agent in self.agents.items():
    if agent.status != "offline" and agent.is_alive():
        tasks.push(self._push_and_collect(agent))  # BUG: list.push() 不存在！
```

---

### P0-6: 围合系统未实现

**PRD 要求**: 墙壁+门围合形成封闭空间，提供辐射免疫，面积上限 64 格，增量检测。

**实际代码**: `invalidate_enclosures_near()` 被调用但**方法不存在**！

```python
# server/engine/game.py:531-532
if building_type in ("wall", "door"):
    self.world.invalidate_enclosures_near(tx, ty)  # 方法不存在！
```

**位置**: `server/engine/game.py:531`

**验证**: `server/engine/world.py` 中没有 `invalidate_enclosures_near` 方法定义。`is_in_enclosure()` 方法始终返回 `False`（需要进一步验证）。

---

## 四、🟡 重要问题 (P1)

### P1-1: 耐久度系统逻辑错误

**问题**: 耐久度增加 = 损坏？

```python
# server/engine/game.py:355-358
if tool and agent.equipment.main_hand:
    agent.equipment.main_hand.durability += 1  # 使用一次 +1？
    if tool.durability_max > 0 and agent.equipment.main_hand.durability >= tool.durability_max:
        agent.equipment.main_hand = None  # 损坏
```

**PRD 语义**: `durability` 应该表示**剩余耐久**，使用一次 `-1`，到 0 时损坏。

**代码语义**: `durability` 从 0 开始累加，到 `durability_max` 时损坏。这与直觉和 PRD 相反。

**同样问题**: 武器耐久也用了同样的逻辑 (`game.py:607-610`)。

---

### P1-2: 生物 AI 过于简化

| PRD 要求 | 实际实现 | 差距 |
|---------|---------|------|
| 8 种生物，各有不同 HP/攻击/行为 | 只有通用生物模板，无个体属性差异 | 生物无差异化 |
| 主动型: 巡逻→仇恨→追击→攻击→脱离 | 只有 IDLE/PATROL/CHASE/ATTACK | 缺少 AGGRO 状态 |
| 被动型: 静止→反击→脱离 | 未实现被动型 | 所有生物都是主动型 |
| 生物属性表 (HP/攻击/速度/仇恨范围) | 硬编码默认值 (HP=30, 伤害=5, 范围=4) | 无个体差异 |
| 生物刷新规则 (区域上限, 2%/tick) | 未实现刷新系统 | 生物不会重生 |
| 生物掉落 (5 种资源, 主+副掉落) | 固定掉落 acid_blood×1 | 掉落系统未实现 |

**位置**: `server/engine/game.py:1016-1084`

---

### P1-3: 地面物品系统与 PRD 不符

| PRD 要求 | 实际代码 | 问题 |
|---------|---------|------|
| 物品永不消失 | **无超时机制** | ✅ 正确（但 PRD v0.9.1 写 900 tick） |
| 单格堆叠上限，超上限分相邻格 | `MAX_GROUND_ITEMS_PER_TILE = 3` 限制种类数 | 限制的是**种类数**而非**堆叠数** |
| 同种物品自动合并 | 未实现合并 | 地面物品不堆叠 |

**位置**: `server/models/__init__.py:125`, `server/engine/game.py:655-664`

---

### P1-4: 视野系统错误

```python
# server/models/__init__.py:416-417
if in_enclosure:
    return 1  # 围合内视野 = 1？应该是围合区域大小！
```

**PRD**: 围合区域有地板时"可见整个围合区域"，无地板时按正常视野。

**实际**: 围合内视野硬编码为 1，几乎等于盲的。

---

### P1-5: 地图生成算法性能隐患

**问题**: 使用 MD5 hash 作为噪声函数，每格生成需要多次 MD5 计算。

```python
# server/engine/world.py:20-23
def _hash_coord(x: int, y: int, seed: int) -> float:
    h = hashlib.md5(f"{seed}:{x}:{y}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF
```

**影响**: 400×400 = 160,000 格，每格 3-4 次 MD5，生成耗时可能达数秒。建议改用 `random.Random(seed).random()` 或 numpy。

---

### P1-6: 配置硬编码与 PRD 不符

| 配置项 | PRD 要求 | 实际代码 | 问题 |
|--------|---------|---------|------|
| 地图尺寸 | 400×400 | 100×100 | 已提 |
| 辐射风暴间隔 | 300~600 tick | 300~600 tick | ✅ 正确 |
| 木质再生范围 | ≤3 格 | 3 格 | ✅ 正确 |
| 木质再生时间 | 600 tick | 600 tick | ✅ 正确 |
| 围合面积上限 | 64 格 | 64 格 | ✅ 正确 |
| 能源节点容量 | 100 | 100 | ✅ 正确 |
| 太阳能充电 | +5/tick | +5/tick | ✅ 正确 |
| 角色无线充电 | +2/tick | +2/tick | ✅ 正确 |
| 内置太阳能 | +1/tick | +1/tick | ✅ 正确 |
| 休息恢复 | +3/tick | +3/tick | ✅ 正确 |

---

### P1-7: 缺少关键系统

| 系统 | 状态 | 说明 |
|------|------|------|
| 碇⇄币转换 | ❌ 未实现 | 经济核心缺失 |
| 门开关/锁住 | ❌ 未实现 | 围合系统不完整 |
| 储物箱交互 | ❌ 未实现 | `use storage deposit/withdraw` 未处理 |
| 建筑修复 | ❌ 未实现 | `repair` action 未处理 |
| 降落仓拆解/搬迁 | ❌ 未实现 | 只有固定出生点 |
| 新手教程系统 | ❌ 未实现 | `tutorial_phase` 字段存在但无逻辑 |
| 无线电信道 | ❌ 未实现 | 只有广播/私聊/扫描 |
| 面对面对话 | ⚠️ 部分实现 | 需要同格，但 `manhattan_distance > 0` 判断错误 |

---

### P1-8: 面对面对话范围判断错误

```python
# server/engine/game.py:886
if agent.position.manhattan_distance(target.position) > 0:
    return ActionResult(..., detail="Must be on same tile for face-to-face talk")
```

**问题**: 曼哈顿距离 > 0 意味着**不同格**就不能对话。但 PRD 说"同一格内面对面交谈"。这个判断是正确的，但错误信息应该更清楚。实际上代码逻辑是对的，但注释有误导。

---

## 五、🟢 中等问题 (P2)

### P2-1: 代码风格与类型安全

- `tasks.push()` — Python list 没有 push 方法，应为 `append()`
- `__import__` 在运行时代码中动态导入 — 应改为顶层 import
- 多处 `import random as rng` 在方法内部 — 应移到模块顶部
- `AgentDisposition` 枚举定义但未使用

### P2-2: 测试覆盖不足

- 有 575 行测试代码，但主要覆盖数据模型和基础公式
- 缺少测试:
  - 行动结算端到端测试
  - 战斗系统测试
  - 合成/建造系统测试
  - 地图生成测试
  - Agent 通信测试

### P2-3: 前端过于简单

- 纯 HTML/CSS/JS 单文件，无框架
- Canvas 渲染性能在 400×400 地图下存疑
- 无 WebSocket 实时更新，只有 SSE
- 注册页面是静态 HTML，无实际 API 调用

### P2-4: 缺少持久化

- 所有状态存储在内存中
- 服务器重启 = 世界重置
- PRD 要求 PostgreSQL + Redis

### P2-5: 无并发控制

- 多个 Agent 同时操作同一格子/物品无锁机制
- `pickup` 先到先得但无原子性保证

---

## 六、✅ 做得好的地方

| 方面 | 说明 |
|------|------|
| **分层架构** | api/ /engine/ /models/ 分层清晰 |
| **数据模型完整** | Agent/Tile/Item/Building/Creature 定义完整 |
| **行动处理器模式** | `_get_action_handler()` 字典映射清晰可扩展 |
| **视野系统框架** | 考虑了昼夜、高地、辐射风暴、探照灯等因素 |
| **战斗公式** | 命中判定、伤害计算、距离衰减基本符合 PRD |
| **测试存在** | 有 pytest 测试覆盖核心数据模型 |
| **快照工具** | `tools/render_snapshots.py` 可生成地图可视化 |
| **CORS 配置** | 前端开发友好 |

---

## 七、与 PRD v0.9.1 一致性详细对比

### 7.1 完全一致 ✅

- 角色属性系统 (CON/AGI/PER)
- 移动速度公式
- 能量消耗基础值
- 昼夜周期 (900 tick)
- 天气系统框架
- 区域辐射概率
- 物品分类 (7 大类)

### 7.2 部分一致 ⚠️

- 物品数据库 — 物品存在但命名/数值错误
- 配方系统 — 配方存在但材料/数量错误
- 战斗系统 — 公式正确但缺少部分特性
- 通信系统 — 广播/私聊/扫描有，信道/面对面不完整

### 7.3 完全不符 ❌

- 地图尺寸 (100 vs 400)
- 碇⇄币经济系统 (未实现)
- 围合系统 (未实现)
- 能源节点储电 (用 hp 代理)
- Agent 通信驱动 (未实现)
- 生物 AI (过于简化)
- 新手教程 (未实现)
- 降落仓系统 (只有固定重生)

---

## 八、建议

### 8.1 短期 (如要基于此分支迭代)

1. **修复 P0-5** — 实现 Agent HTTP 推送循环（最高优先级）
2. **修复 P0-4** — 给 Building 添加 `stored_power` 字段
3. **修复 P0-6** — 实现围合检测（flood-fill + 增量更新）
4. **修复 P1-1** — 耐久度语义反转（剩余耐久而非累计损坏）
5. **统一术语** — `slab` → `ingot`，补充金币/铁币/铜币

### 8.2 中期

1. 地图尺寸改为 400×400 或配置化
2. 实现碇⇄币双向转换
3. 实现生物刷新和差异化 AI
4. 添加 PostgreSQL 持久化层
5. 完善测试覆盖

### 8.3 长期

1. **不建议在此代码基础上继续** — 架构问题（单进程、全内存）难以支撑 50+ Agent
2. 建议参考此实现的**数据模型设计**和**行动处理器模式**
3. 重新设计时考虑:
   - 异步 Actor 模型或 ECS 架构
   - Redis 作为 tick 状态缓存
   - PostgreSQL 作为持久化
   - 地图分片支持水平扩展

---

## 九、问题汇总表

| 编号 | 问题 | 严重度 | 位置 | 修复建议 |
|------|------|--------|------|---------|
| P0-1 | 地图尺寸 100×100 (应为 400×400) | 🔴 | `api/main.py:35` | 改为 400×400 或配置化 |
| P0-2 | 配方材料数量和名称错误 | 🔴 | `models/recipes.py` | 对照 PRD 7.4.2 修正 |
| P0-3 | 物品术语不符 (slab≠ingot) | 🔴 | `models/items.py` | 统一为 PRD 术语 |
| P0-4 | 能源节点用 hp 代理储电 | 🔴 | `engine/game.py` | Building 添加 stored_power |
| P0-5 | Tick 未驱动 Agent 通信 | 🔴 | `api/main.py` | 实现 HTTP 推送 + 收集 |
| P0-6 | 围合系统未实现 | 🔴 | `engine/world.py` | 实现 flood-fill + 增量检测 |
| P1-1 | 耐久度语义相反 | 🟡 | `engine/game.py` | 改为剩余耐久模式 |
| P1-2 | 生物 AI 过于简化 | 🟡 | `engine/game.py` | 实现完整状态机 |
| P1-3 | 地面物品系统不符 | 🟡 | `models/__init__.py` | 实现堆叠 + 溢出分配 |
| P1-4 | 围合内视野=1 | 🟡 | `models/__init__.py` | 按 PRD 实现 |
| P1-5 | MD5 噪声性能差 | 🟡 | `engine/world.py` | 改用 random 或 numpy |
| P1-7 | 多个系统缺失 | 🟡 | 多处 | 按 PRD 逐项实现 |
| P2-1 | 代码风格问题 | 🟢 | 多处 | 修复 list.push 等问题 |
| P2-4 | 无持久化 | 🟢 | 全局 | 添加 PostgreSQL |

---

*评审完成。建议产品团队确认是否基于此分支继续迭代，还是重新设计架构。*

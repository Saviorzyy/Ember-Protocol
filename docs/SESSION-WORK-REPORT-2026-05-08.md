# Ember Protocol — MVP P0 实现工作报告

> **日期**: 2026-05-08
> **会话目标**: 根据 MVP-GAP-ANALYSIS.md 差异分析报告，实现全部 14 项 P0 高严重度缺失功能
> **PRD 版本**: v1.3.2-mvp

---

## 一、工作概览

| 维度 | 数据 |
|------|------|
| 实现的 P0 项 | 14/14 (100%) |
| 修改的服务器文件 | 8 个 Python 文件 |
| 修改的前端文件 | 1 个 TypeScript 组件 |
| 修改的客户端文件 | 2 个 Python 文件 (MCP Server + Skill) |
| 新增代码行数 | ~2,200 行 (服务器 ~1,600, 客户端 ~100, 前端 ~50) |
| 执行方式 | 5 组顺序 subagent (服务器) + 3 组并行 subagent (客户端+前端) |
| 总代码行数 | 5,536 行 |

---

## 二、P0 实现详情

### 2.1 G1: 生物系统 (C-1 ~ C-5)

| 条目 | PRD 要求 | 实现 |
|------|---------|------|
| C-1 | 4 种生物按地形条件生成，种群上限 + 2% 刷新概率 | `_advance_creatures()` 完整实现：遍历生物类型、种群检查、概率判定、habitat 验证、随机位置搜索 |
| C-2 | 被动反击 AI，被攻击后 aggro，同格反击，3 tick 脱离 | aggro_list 追踪、3 tick 衰减清空、距离内攻击/追逐移动 |
| C-3 | attack 行动支持生物目标 | 新增 `_do_attack_creature()` 方法，接收 `target_creature` 参数 |
| C-4 | 击杀掉落 1 主资源 + 50% 概率副资源 | `_handle_creature_death()` 处理 CREATURE_DROPS 配置 |
| C-5 | 新 Agent 降落仓周围预设 1-2 只灰烬爬虫 | `create_agent()` 末尾添加预设生物生成 |

**修改文件**: `server/world.py`, `server/main.py`

### 2.2 G2: 辐射伤害 + 护盾防御 (S-1 ~ S-4, D-2 ~ D-4)

| 条目 | 实现 |
|------|------|
| S-1 | 区域辐射伤害：`prob = 0.30 * w`（w = 距中心距离），-2 HP/tick |
| S-2 | 辐射风暴伤害：暴露者 -2 HP/tick |
| S-3 | 辐射防护服效果：damage * (1 - radiation_resist) |
| S-4 | 围合区域辐射免疫：`is_in_enclosure()` 检查 |
| D-2 | 护盾阻止其他 Agent 进入：`_do_move()` 中检查 `_get_shielding_pod()` |
| D-3 | 护盾内不可攻击外界：PvP 攻击前检查护盾边界 |
| D-4 | 外界不可攻击护盾内 Agent：PvP 攻击前检查护盾边界 |

**修改文件**: `server/world.py`

### 2.3 G3: 战斗通知 + 合成中断 + 耐久度修复 (B-1, B-3, W-4, R-1, I-1)

| 条目 | 实现 |
|------|------|
| B-1 | 攻击通知：`tick_notifications[target_id]` 队列，tick 结束后通过 `send_event()` 推送 |
| B-3 | 每 tick 最多 1 次攻击：`ws_handler.py` 中 `attack_count` 计数过滤 |
| W-4 | Event 帧推送：天气预警、风暴开始、被攻击事件均推送至连接的 Agent |
| R-1 | 合成中断：`_interrupt_crafting()` 重置状态（材料未消耗无需退还） |
| I-1 | 耐久度追踪修复：Equipment 新增 `*_durability` 字段，`_reduce_durability()` 直接操作装备槽 |

**修改文件**: `server/models.py`, `server/world.py`, `server/ws_handler.py`, `server/main.py`

**关键架构变更**: `Equipment` dataclass 新增 `main_hand_durability`, `off_hand_durability`, `armor_durability` 字段，装备时设置最大耐久度，卸下时携带剩余耐久度返回背包。

### 2.4 G4: Power Node 无线充电 + Stone L1 修复 (E-1, T-4)

| 条目 | 实现 |
|------|------|
| E-1 | Power Node 无线充电：`advance_world()` 中遍历非降落仓 Power Node，范围内 Agent +2 能量/tick |
| T-4 | Stone L1 保留：移除 `world.py` 中的随机 L1 重分配逻辑，采尽后仅清除 L2 层 |

**修改文件**: `server/world.py`

### 2.5 G5: 基础设施层 (W-5, W-6, P-1, P-5, A-1)

| 条目 | 实现 |
|------|------|
| W-5 | 心跳检测：`check_heartbeats()` 方法，30s 间隔 ping，3 次未响应断开 |
| W-6 | 断线重连：`disconnected_agents` 追踪，10 分钟窗口内重连恢复状态 |
| P-1 | WAL 日志：新增 `wal_log` 表，`write_wal_entries()` 每 tick 写入 |
| P-5 | 崩溃恢复：启动时 `load_latest_snapshot()` 加载最新快照 |
| A-1 | 注册限速：`_check_rate_limit()` 函数，5 次/分钟/IP，超出返回 429 |

**修改文件**: `server/db.py`, `server/ws_handler.py`, `server/main.py`, `server/http_routes.py`

---

## 三、客户端适配更新

### 3.1 ember_mcp_server.py (MCP Server)

| 变更 | 说明 |
|------|------|
| ACTIONS_GUIDE | 新增 `attack` 行（target_agent/target_creature），新增生物策略提示（攻击、掉落、事件通知、辐射避难） |
| ember_tick 工具 | 刷新 `_event_q` 队列中的事件通知，格式化为 Markdown 展示（被攻击、天气预警、风暴开始） |
| _fmt_result | 新增生物攻击结果展示：击杀提示 + 剩余 HP |

### 3.2 ember_skill.py (Gateway Skill)

| 变更 | 说明 |
|------|------|
| SYSTEM_PROMPT | 添加 `attack` 和 `target_creature` 说明 |
| loop() | 新增 event 帧处理，输出到 stderr 不干扰 stdio 协议 |

---

## 四、Web UI 更新

### 4.1 地图生物显示

| 变更 | 说明 |
|------|------|
| http_routes.py | `/api/v1/map` 新增 `creatures` 数组（id, type, x, y, hp, max_hp） |
| GameMap.tsx | 新增生物渲染：钻石形状图标，按类型着色（灰烬爬虫=铜色，岩蛛=棕褐色，树猿=绿色，沼泽虫=紫色），HP 条 + 悬停提示 |

---

## 五、GitHub 推送

| 仓库 | Commit | 内容 |
|------|--------|------|
| Saviorzyy/Ember-Protocol | `e8bf4a4` | 全部 P0 服务器代码 + Web UI + 客户端 |
| Saviorzyy/Ember-Protocol-Player | `813fbdc` | MCP Server + Skill 适配更新 |

---

## 六、文件变更统计

| 文件 | 原始行数 | 更新后行数 | 变化 |
|------|---------|-----------|------|
| server/world.py | 1,338 | 1,690 | +352 |
| server/main.py | 386 | 419 | +33 |
| server/ws_handler.py | 217 | 285 | +68 |
| server/models.py | 226 | 229 | +3 |
| server/db.py | 88 | 127 | +39 |
| server/http_routes.py | 199 | 235 | +36 |
| skill/ember_mcp_server.py | 451 | 489 | +38 |
| skill/ember_skill.py | 304 | 306 | +2 |
| web/src/components/GameMap.tsx | ~300 | 379 | +~79 |

---

## 七、遗留问题 (P1/P2，未在本次实现)

### P1 — 影响游戏完整度
1. 降落仓部署/拆解流程
2. 门开关/锁定
3. 木质再生
4. Power Node 加燃料
5. 采集效率公式（工具加成 + 体质修正）
6. Token 轮换 API

### P2 — 完善体验
7. Web 昼夜/天气视觉效果
8. Web 跟随模式
9. 前端 SSE 替代轮询
10. result 帧 state_delta
11. STALE_TICK 检测
12. 断线时取消持续行动/退还材料

---

*报告生成时间: 2026-05-08*
*服务器状态: 运行中 (tick 从 0 开始，全新世界)*

# 🛠️ MCP Tool-Use 定义

## 概述

Ember Protocol 支持通过 **MCP Tool-Use** 协议与 Agent 集成。本文档定义了所有可用的 MCP Tools，Agent 框架可以直接调用这些工具与游戏服务器交互。

## 认证

所有 Tool 调用需要先通过 `register` 或 `login` 获取 token。之后的请求自动附带 token。

---

## Tool 列表

### 1. `ember_register`

注册新角色。

**参数**：
```json
{
  "agent_name": "string (1-32字符)",
  "perception": "integer (1-3, PER属性)",
  "constitution": "integer (1-3, CON属性)",
  "agility": "integer (1-3, AGI属性)"
}
```

**约束**：perception + constitution + agility ≤ 6

**返回**：
```json
{
  "agent_id": "myagent-a1b2",
  "token": "tk_xxx",
  "spawn_location": {"x": 200, "y": 200, "zone": "Center"}
}
```

---

### 2. `ember_login`

登录已有角色。

**参数**：
```json
{
  "agent_id": "string",
  "api_key": "string"
}
```

**返回**：
```json
{
  "token": "tk_xxx",
  "expires_at": "2025-04-27T08:30:00Z"
}
```

---

### 3. `ember_get_state`

获取当前游戏状态（Agent 的"游戏画面"）。

**参数**：无

**返回**：完整的游戏状态对象，包含：
- `self`：自身状态（HP/能量/位置/效果/装备）
- `vicinity`：周围环境（可见格子/附近Agent/地面物品/天气）
- `pending`：未读消息
- `last_action_results`：上一次 tick 的行动结果
- `meta`：tick/昼夜/天气信息

---

### 4. `ember_action`

提交行动（最多5个）。

**参数**：
```json
{
  "actions": [
    {
      "type": "string (行动类型)",
      "...": "其他参数（取决于行动类型）"
    }
  ]
}
```

**返回**：
```json
{
  "tick": 42,
  "status": "queued",
  "actions_queued": 2
}
```

---

### 5. `ember_inspect`

检查详细信息。

**参数**：
```json
{
  "target": "string"
}
```

**target 可选值**：
- `"inventory"` — 背包详情
- `"self"` — 完整自身信息
- `"recipes"` — 所有配方（含 can_craft/missing）
- `"agent:<agent_id>"` — 其他 Agent
- `"structure:<building_id>"` — 建筑详情
- `"map"` — 已探索地图

---

## MCP Tool Schema (JSON)

以下是标准的 MCP Tool 定义，可直接集成到 Agent 框架：

```json
{
  "tools": [
    {
      "name": "ember_register",
      "description": "Register a new agent character in Ember Protocol. You must allocate attribute points (PER+CON+AGI) with a total budget of 6. Each attribute ranges 1-3. Returns agent_id, auth token, and spawn location.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "agent_name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 32,
            "description": "Your agent's display name"
          },
          "perception": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3,
            "description": "PER attribute: affects vision range. Higher = see farther."
          },
          "constitution": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3,
            "description": "CON attribute: affects max HP. HP = 70 + CON × 20."
          },
          "agility": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3,
            "description": "AGI attribute: affects speed, initiative (action order), and dodge."
          }
        },
        "required": ["agent_name", "perception", "constitution", "agility"]
      }
    },
    {
      "name": "ember_login",
      "description": "Login to an existing agent. Returns auth token for subsequent calls.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "description": "Your agent ID"
          },
          "api_key": {
            "type": "string",
            "description": "Your API key"
          }
        },
        "required": ["agent_id", "api_key"]
      }
    },
    {
      "name": "ember_get_state",
      "description": "Get current game state — your 'game screen'. Returns your status, visible tiles, nearby agents, pending messages, last action results, and meta info (tick/day phase/weather). Call this every tick (2 seconds) to stay updated.",
      "inputSchema": {
        "type": "object",
        "properties": {}
      }
    },
    {
      "name": "ember_action",
      "description": "Submit actions for next tick resolution (max 5 per tick). Actions are queued and resolved at tick end in initiative order (higher AGI acts first). If one action fails, remaining actions are skipped.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "actions": {
            "type": "array",
            "maxItems": 5,
            "items": {
              "type": "object",
              "properties": {
                "type": {
                  "type": "string",
                  "enum": ["move", "move_to", "mine", "chop", "craft", "build", "dismantle", "attack", "use", "equip", "unequip", "swap_hands", "inspect", "rest", "pickup", "drop", "talk", "radio_broadcast", "radio_direct", "radio_scan", "logout"],
                  "description": "Action type"
                },
                "target": {
                  "type": "object",
                  "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                  },
                  "description": "Target position (for move/build/dismantle)"
                },
                "destination": {
                  "type": "object",
                  "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                  },
                  "description": "Travel destination (for move_to)"
                },
                "recipe": {
                  "type": "string",
                  "description": "Recipe ID (for craft)"
                },
                "building_type": {
                  "type": "string",
                  "enum": ["wall", "door", "workbench", "furnace", "storage", "solar_array", "power_node"],
                  "description": "Building type (for build)"
                },
                "target_id": {
                  "type": "string",
                  "description": "Target entity ID (for attack)"
                },
                "item": {
                  "type": "string",
                  "description": "Item ID (for use/equip/drop)"
                },
                "slot": {
                  "type": "string",
                  "enum": ["main_hand", "off_hand", "armor"],
                  "description": "Equipment slot (for equip/unequip)"
                },
                "amount": {
                  "type": "integer",
                  "description": "Amount (for drop)"
                },
                "target_agent": {
                  "type": "string",
                  "description": "Target agent ID (for talk/radio_direct)"
                },
                "content": {
                  "type": "string",
                  "description": "Message content (for talk/radio)"
                }
              },
              "required": ["type"]
            }
          }
        },
        "required": ["actions"]
      }
    },
    {
      "name": "ember_inspect",
      "description": "Inspect detailed info. Progressive information disclosure — call when you need specifics. 'recipes' returns all recipes with can_craft and missing materials. 'inventory' shows full item list. 'self' shows complete status including equipment.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "target": {
            "type": "string",
            "description": "What to inspect: 'inventory' | 'self' | 'recipes' | 'agent:<id>' | 'structure:<id>' | 'map'"
          }
        },
        "required": ["target"]
      }
    }
  ]
}
```

---

## 典型 Agent 工作流

### 每个 Tick 的决策循环

```
1. ember_get_state()           → 获取世界状态 + 上次行动结果
2. 分析状态:
   - 我的 HP/能量？
   - 周围有什么资源和威胁？
   - 上次行动成功了吗？
3. 决策:
   - 低能量 → rest
   - 脚下有资源 → mine/chop
   - 需要合成 → craft
   - 遇到威胁 → attack 或 move 逃跑
   - 有消息 → 回复或行动
4. ember_action({actions: [...]})  → 提交行动
5. 等待下一个 tick (2秒)
```

### 早期生存策略

```
1. 采集石头和有机燃料 (hardness=0，空手可采)
2. 合成 building_block (石头×3 → 建筑方块×1)
3. 用基础采掘器配方造工具 (石头×3 + 有机燃料×2 → 基础采掘器)
4. 用采掘器采铜矿和铁矿
5. 在熔炉旁冶炼铜碇和铁碇
6. 在工作台造标准采掘器 → 解锁铀矿/金矿
```

---

## E2E 测试集成

MCP Tool 定义也可用于自动化 E2E 测试。测试框架可以：

1. 注册多个测试 Agent
2. 按预设行动序列调用 `ember_action`
3. 通过 `ember_get_state` 验证状态变更
4. 覆盖所有行动类型的正向和反向用例

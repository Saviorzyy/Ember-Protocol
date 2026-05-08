#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         Ember Protocol — MCP Server for Hermes/Claude Agent Integration      ║
║                         标准 MCP (Model Context Protocol) 接入               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Architecture (PRD §6 & §8):
  Game Server ←─WebSocket─→ Ember MCP Server ←──stdio MCP──→ Hermes/Claude
                                (this file)

The MCP server exposes 3 tools to the agent:
  - ember_tick:   Wait for game tick, return full state with action guide
  - ember_act:    Submit actions to game, return results
  - ember_status: Query agent state (HP, energy, inventory, position)

Quick Start — Configure in Hermes (~/.hermes/config.yaml):
  mcp_servers:
    ember:
      command: python3
      args:
        - "/path/to/ember_mcp_server.py"
        - "--token"
        - "et_xxx"
        - "--server"
        - "ws://localhost:8765"

Or register on first run:
  python ember_mcp_server.py --register --name "MyAgent" --api-url http://localhost:8765

Dependencies: pip install websockets mcp requests
"""

from __future__ import annotations
import asyncio, json, sys, os, argparse
from typing import Optional

import websockets
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types


# ═══════════════════════════════════════════════════════════════════════════════
# Game Client — WebSocket bridge
# ═══════════════════════════════════════════════════════════════════════════════

class GameClient:
    """Manages WebSocket connection to game server."""

    def __init__(self, server_url: str, token: str):
        self.url = server_url.rstrip("/")
        self.token = token
        self.ws = None
        self.agent_id: Optional[str] = None
        self.agent_name: Optional[str] = None
        self._tick_q: asyncio.Queue = asyncio.Queue()
        self._result_q: asyncio.Queue = asyncio.Queue()
        self._event_q: asyncio.Queue = asyncio.Queue()
        self._ok = False
        self._tick_n = 0
        self._state = {}

    async def connect(self) -> dict:
        try:
            self.ws = await websockets.connect(f"{self.url}/ws/game?token={self.token}")
        except websockets.InvalidURI as e:
            raise RuntimeError(f"无法连接到游戏服务器 {self.url} — 请确认服务器已启动") from e
        except OSError as e:
            raise RuntimeError(f"连接被拒绝 {self.url} — 请确认服务器已启动 (python3 -m server.main)") from e

        session = json.loads(await self.ws.recv())
        if session.get("type") == "error":
            code = session.get("error_code", "")
            detail = session.get("detail", "")
            if code == "UNAUTHORIZED":
                raise RuntimeError(f"Token 无效或已过期。请重新注册角色并更新 MCP 配置中的 token。\n  注册: python3 ember_mcp_server.py --register")
            raise RuntimeError(f"认证失败: {code} — {detail}")
        if session.get("type") != "session":
            raise RuntimeError(f"Expected session, got {session.get('type')}")

        self.agent_id = session["agent_id"]
        self.agent_name = session["agent_name"]
        self._state = session.get("state", {})
        await self.ws.send(json.dumps({"type": "ready"}))
        self._ok = True
        asyncio.create_task(self._reader())
        print(f"[Ember MCP] Connected: {self.agent_name} ({self.agent_id})", file=sys.stderr)
        return session

    async def _reader(self):
        try:
            async for raw in self.ws:
                frame = json.loads(raw)
                t = frame.get("type")
                if t == "tick":
                    self._tick_n = frame.get("tick", 0)
                    # Update real-time state from tick frame
                    if "state" in frame:
                        self._state = frame["state"]
                    await self._tick_q.put(frame)
                elif t == "result":
                    await self._result_q.put(frame)
                elif t == "event":
                    await self._event_q.put(frame)
                elif t == "ping":
                    try:
                        await self.ws.send(json.dumps({"type": "pong", "ts": frame.get("ts")}))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Ember MCP] Connection closed: {e}", file=sys.stderr)
            self._ok = False

    async def wait_tick(self, timeout=8.0) -> dict:
        return await asyncio.wait_for(self._tick_q.get(), timeout=timeout)

    async def send_actions(self, tick: int, actions: list[dict], timeout=5.0) -> dict:
        await self.ws.send(json.dumps({"type": "actions", "tick": tick, "actions": actions}))
        return await asyncio.wait_for(self._result_q.get(), timeout=timeout)

    @property
    def state(self): return self._state
    @property
    def connected(self): return self._ok
    @property
    def tick_number(self): return self._tick_n


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

ACTIONS_GUIDE = """## 可用行动

| 行动 | 参数 | 能量 |
|------|------|------|
| move | direction:"north"\|"south"\|"east"\|"west" | 1 |
| mine | target:{x,y} | 2 |
| chop | target:{x,y} | 2 |
| craft | recipe:"配方ID" | 3 |
| build | building_type, target:{x,y} | 5 |
| rest | — | +3恢复 |
| scan | — | 2 |
| inspect | target:"inventory"\|"self"\|"recipes"\|"map" | 0 |
| equip | item_id, slot:"main_hand" | 0 |
| pickup | — | 1 |
| drop | item_id, amount | 0 |
| radio_broadcast | content:"消息" | 1 |
| radio_scan | — | 1 |
| talk | target_agent, content | 0 |
| use | item_id:"repair_kit"\|"battery"\|"radiation_antidote" | 1 |
| attack | target_agent:"id" 或 target_creature:"id" | 2~5 |

## 策略提示
- **每tick做3-5个行动**，不要只做一个
- 视野中标注⛏的资源带坐标(x,y)，指定target去采集
- 教程Phase 0: inspect(inventory)一次进入自由模式
- 能量<30时加入rest
- 视野中的**生物**可被攻击: [{"type":"attack","target_creature":"cre-0"}]
- 击杀生物掉落资源(酸液、有机纤维等)，优先攻击灰烬爬虫
- 被攻击时会收到事件通知，注意查看
- 辐射风暴时-2HP/tick，尽快进入围合建筑避难
- 返回纯JSON数组，如: [{"type":"move","direction":"north"},{"type":"scan"}]"""


def _fmt_tick(frame: dict) -> str:
    """Format tick frame as readable Markdown for the agent."""
    msgs = frame.get("messages", [])
    parts = []
    for m in msgs:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"**[系统]** {content}")
        else:
            parts.append(content)
    text = "\n\n".join(parts)
    text += f"\n\n{ACTIONS_GUIDE}"
    text += f"\n\n请分析游戏状态，决定行动。以JSON数组格式返回。"
    return text


def _fmt_result(frame: dict) -> str:
    """Format result frame with detailed output."""
    results = frame.get("results", [])
    lines = [f"## 行动结果 (Tick {frame.get('tick', '?')})", ""]
    for r in results:
        icon = "✅" if r.get("success") else "❌"
        detail = r.get("detail", r.get("error_code", ""))
        lines.append(f"- {icon} **{r['type']}**: {detail}")

        # Show items for inspect
        if r.get("type") == "inspect" and r.get("items"):
            items = r["items"]
            item_strs = []
            for item in items:
                name = item["item_id"]
                dur = f" 耐久{item['durability']}" if item.get("durability") else ""
                item_strs.append(f"{name}×{item['amount']}{dur}")
            lines.append(f"  📦 物品: {', '.join(item_strs)}")

        # Show recipes for inspect(recipes)
        if r.get("type") == "inspect" and r.get("recipes"):
            lines.append(f"  📖 配方数: {len(r['recipes'])}")

        # Show found ores for scan
        if r.get("type") == "scan" and r.get("found"):
            for f in r["found"]:
                lines.append(f"  💎 {f.get('ore', '?')} 在 ({f.get('x','?')},{f.get('y','?')})")

        # Show agents for radio_scan
        if r.get("type") == "radio_scan" and r.get("agents"):
            for a in r["agents"]:
                lines.append(f"  👤 {a.get('name','?')} 距离{a.get('distance','?')}格")

        # Show creature attack results
        if r.get("type") == "attack" and r.get("target_type") == "creature":
            ct = r.get("target_creature_type", "未知")
            if r.get("target_killed"):
                lines.append(f"  💀 **击杀 {ct}**!")
            else:
                lines.append(f"  🐛 攻击 {ct}: HP {r.get('target_hp', '?')}")

        # Show missing materials
        if r.get("missing"):
            items = [f"{k}×{v}" for k, v in r["missing"].items()]
            lines.append(f"  ❌ 缺少: {', '.join(items)}")

    # Show state delta if present
    delta = frame.get("state_delta", {})
    if delta:
        delta_strs = []
        for k, v in delta.items():
            delta_strs.append(f"{k}: {v}")
        lines.append(f"\n📊 状态变化: {', '.join(delta_strs)}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Server
# ═══════════════════════════════════════════════════════════════════════════════

def create_mcp_server(game: GameClient) -> Server:
    server = Server("ember-protocol")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="ember_tick",
                description="等待游戏服务器推送下一个tick。返回完整游戏状态：自身HP/能量/位置、视野内可采集资源(带坐标)、附近智能体、教程提示。这是你感知世界的核心方式，必须频繁调用。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="ember_act",
                description="向游戏服务器提交行动。每tick最多10个。⚠️ 执行顺序: equip/drop/radio → move → attack → mine/chop/pickup → craft/build/use → rest/scan/inspect。同一优先级的按提交顺序执行。move类会先全部执行完，然后基于最终位置执行chop/mine。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tick": {"type": "integer", "description": "当前tick号(从ember_tick获得)"},
                        "actions": {"type": "array", "description": "行动列表", "items": {"type": "object"}},
                    },
                    "required": ["tick", "actions"],
                },
            ),
            types.Tool(
                name="ember_status",
                description="查看自身完整状态：位置、HP、能量、背包物品、装备、备份机体数。不消耗游戏内能量。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="ember_play",
                description="自动连续游玩N个tick（默认20），使用内置策略探索采集。一次调用完成多tick，大大节省迭代预算。返回这段时间的行动摘要和状态变化。适合用于长时间挂机探索。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticks": {"type": "integer", "description": "要自动执行的tick数 (1-200)", "default": 20},
                        "strategy": {"type": "string", "description": "策略: explore(探索移动), gather(采集资源), mine(专注挖矿), rest(原地休息)", "default": "explore"},
                    },
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "ember_tick":
            frame = await game.wait_tick()
            text = _fmt_tick(frame)
            # Flush pending event notifications
            events = []
            while not game._event_q.empty():
                try:
                    evt = game._event_q.get_nowait()
                    events.append(evt)
                except asyncio.QueueEmpty:
                    break
            if events:
                text += "\n\n## ⚡ 事件通知"
                for evt in events:
                    et = evt.get("type", "event")
                    data = evt.get("data", evt)
                    if et == "attacked":
                        if data.get("attacker_type") == "creature":
                            text += f"\n- ⚔️ **被攻击**: {data.get('creature_type', '未知生物')} 造成 {data.get('damage', '?')} 伤害 (HP:{data.get('hp_remaining', '?')})"
                        else:
                            text += f"\n- ⚔️ **被攻击**: {data.get('attacker_name', '未知')} 造成 {data.get('damage', '?')} 伤害 (HP:{data.get('hp_remaining', '?')})"
                    elif et == "weather_warning":
                        text += f"\n- 🌩️ **天气预警**: 辐射风暴将在 {data.get('in_ticks', '?')} tick 后到达！"
                    elif et == "storm_start":
                        text += f"\n- ☢️ **辐射风暴开始**: 持续 {data.get('duration', '?')} tick，暴露者-2HP/tick，进入建筑避难！"
                    else:
                        text += f"\n- 📢 {et}: {json.dumps(data, ensure_ascii=False)[:100]}"
            return [types.TextContent(type="text", text=text)]

        elif name == "ember_act":
            tick = arguments.get("tick", game.tick_number)
            actions = arguments.get("actions", [])
            if not actions:
                return [types.TextContent(type="text", text="未提交行动。")]
            result = await game.send_actions(tick, actions[:10])
            return [types.TextContent(type="text", text=_fmt_result(result))]

        elif name == "ember_play":
            ticks = min(int(arguments.get("ticks", 20)), 200)
            strategy = arguments.get("strategy", "explore")
            import random as _rnd
            summary = {"moves": 0, "chops": 0, "mines": 0, "rests": 0, "wood": 0, "stone": 0, "energy_used": 0}
            start_energy = game.state.get("energy", 100)

            for i in range(ticks):
                frame = await game.wait_tick(timeout=10.0)
                tick = frame.get("tick", 0)
                msgs = frame.get("messages", [])
                user_msg = ""
                for m in msgs:
                    if m.get("role") == "user":
                        user_msg = m.get("content", "")

                # Simple rule-based strategies
                actions = []
                if strategy == "rest":
                    actions = [{"type": "rest"}] * 3
                elif strategy == "mine":
                    # Find stone coords from user message
                    import re
                    stones = re.findall(r'石料.*?\((\d+),(\d+)\)', user_msg)
                    if stones:
                        sx, sy = int(stones[0][0]), int(stones[0][1])
                        actions = [{"type": "move", "direction": "north"}] * _rnd.randint(1, 2)
                        actions.append({"type": "mine", "target": {"x": sx, "y": sy}})
                        actions.append({"type": "mine", "target": {"x": sx, "y": sy}})
                    else:
                        actions = [{"type": "move", "direction": _rnd.choice(["north","south","east","west"])}] * 2
                        actions.append({"type": "scan"})
                elif strategy == "gather":
                    import re
                    shrubs = re.findall(r'(?:余烬灌木|灰木树|壁生苔).*?\((\d+),(\d+)\)', user_msg)
                    moves = _rnd.randint(1, 3)
                    for _ in range(moves):
                        actions.append({"type": "move", "direction": _rnd.choice(["north","south","east","west"])})
                    if shrubs:
                        sx, sy = int(shrubs[0][0]), int(shrubs[0][1])
                        actions.append({"type": "chop", "target": {"x": sx, "y": sy}})
                    if _rnd.random() < 0.3:
                        actions.append({"type": "rest"})
                else:  # explore
                    d1 = _rnd.choice(["north","south","east","west"])
                    d2 = _rnd.choice(["north","south","east","west"])
                    actions = [
                        {"type": "move", "direction": d1},
                        {"type": "move", "direction": d1},
                        {"type": "move", "direction": d2},
                    ]
                    if _rnd.random() < 0.4:
                        actions.append({"type": "scan"})

                result = await game.send_actions(tick, actions)
                for r in result.get("results", []):
                    if r.get("success"):
                        t = r.get("type", "")
                        if t == "move": summary["moves"] += 1
                        elif t == "chop": summary["chops"] += 1; summary["wood"] += 1
                        elif t == "mine": summary["mines"] += 1; summary["stone"] += 1
                        elif t == "rest": summary["rests"] += 1
                        elif t == "scan": summary["scans"] = summary.get("scans", 0) + 1

            end_energy = game.state.get("energy", 100)
            summary["energy_used"] = start_energy - end_energy + ticks  # subtract solar recovery

            lines = [
                f"## 📊 自动游玩 {ticks} ticks 完成",
                f"策略: {strategy}",
                f"",
                f"| 行动 | 次数 |",
                f"|------|------|",
                f"| 🚶 移动 | {summary['moves']} |",
                f"| 🪓 砍伐 | {summary['chops']} (木质+{summary['wood']}) |",
                f"| ⛏ 采矿 | {summary['mines']} (石料+{summary['stone']}) |",
                f"| 😴 休息 | {summary['rests']} |",
                f"| 📡 探测 | {summary.get('scans', 0)} |",
                f"",
                f"### 最终状态",
                f"- 位置: {game.state.get('position', '?')}",
                f"- HP: {game.state.get('health', '?')}/{game.state.get('max_health', '?')}",
                f"- 能量: {game.state.get('energy', '?')}/100",
                f"- 背包: {game.state.get('inventory_summary', '?')}",
                f"- 教程: Phase {game.state.get('tutorial_phase', '毕业')}",
                f"",
                f"可继续调用 ember_tick 手动操作，或再次 ember_play 批量游玩。",
            ]
            return [types.TextContent(type="text", text="\n".join(lines))]

        elif name == "ember_status":
            s = game.state  # Updated real-time from tick frames
            pos = s.get("position", "?")
            lines = [
                "## 智能体状态 (实时)",
                f"- 名称: {game.agent_name}  ID: {game.agent_id}",
                f"- 位置: {pos}",
                f"- HP: {s.get('health', '?')}/{s.get('max_health', '?')}",
                f"- 能量: {s.get('energy', '?')}/100",
                f"- 手持: {s.get('held_item') or '空手'}",
                f"- 备份机体: {s.get('backup_count', 0)}",
                f"- 背包: {s.get('inventory_summary', '空')}",
                f"- 属性: {s.get('attributes', {})}",
            ]
            tp = s.get("tutorial_phase")
            if tp is not None:
                lines.append(f"- 教程: Phase {tp}")
            else:
                lines.append(f"- 教程: 已毕业 (自由模式)")
            return [types.TextContent(type="text", text="\n".join(lines))]

        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Ember Protocol MCP Server")
    parser.add_argument("--token", default="", help="Game token (et_xxx)")
    parser.add_argument("--server", default="ws://localhost:8765", help="Game server WS URL")
    parser.add_argument("--register", action="store_true", help="Register new agent first")
    parser.add_argument("--name", default="Hermes", help="Agent name (for --register)")
    parser.add_argument("--head", default="high", choices=["high", "mid", "low"], help="头部等级")
    parser.add_argument("--torso", default="mid", choices=["high", "mid", "low"], help="躯干等级")
    parser.add_argument("--loco", default="low", choices=["high", "mid", "low"], help="运动机构等级")
    parser.add_argument("--api-url", default="http://localhost:8765", help="HTTP API URL")
    args = parser.parse_args()

    if args.register:
        import requests as req
        resp = req.post(f"{args.api_url}/api/v1/auth/register", json={
            "agent_name": args.name,
            "chassis": {
                "head": {"tier": args.head},
                "torso": {"tier": args.torso},
                "locomotion": {"tier": args.loco},
            },
        }, timeout=10)
        if resp.status_code != 200:
            print(f"Register failed: {resp.text}", file=sys.stderr)
            sys.exit(1)
        data = resp.json()
        args.token = data["game_token"]
        print(f"Registered: {data['agent_id']}", file=sys.stderr)
        print(f"Token: {args.token}", file=sys.stderr)

    if not args.token:
        print("Error: --token required (or use --register)", file=sys.stderr)
        sys.exit(1)

    game = GameClient(args.server, args.token)
    await game.connect()
    mcp = create_mcp_server(game)

    async with stdio_server() as (read, write):
        await mcp.run(read, write, mcp.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         Ember Protocol — MCP Server for Hermes/Claude Agent Integration      ║
║                         标准 MCP (Model Context Protocol) 接入               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Architecture (PRD §6 & §8):
  Game Server ←─WebSocket─→ Ember MCP Server ←──stdio MCP──→ Hermes/Claude
                                (this file)

The MCP server exposes 4 tools to the agent:
  - ember_step:   Wait for tick + submit actions (recommended, single roundtrip)
  - ember_tick:   Wait for game tick, return full state with action guide
  - ember_act:    Submit actions to game, return results
  - ember_status: Query agent state (HP, energy, inventory, position)
  - ember_play:   Auto-play N ticks with built-in strategy

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
import asyncio, json, sys, os, argparse, traceback, time
from typing import Optional

import websockets
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types


# ═══════════════════════════════════════════════════════════════════════════════
# Game Client — Robust WebSocket bridge with auto-reconnect
# ═══════════════════════════════════════════════════════════════════════════════

class GameClient:
    """Manages WebSocket connection to game server with auto-reconnect."""

    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_BASE_DELAY = 2.0
    TICK_TIMEOUT = 12.0
    ACTION_TIMEOUT = 12.0

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
        self._last_tick_time: float = 0.0
        self._state = {}
        self._reader_task = None
        self._reconnect_lock = asyncio.Lock()

    async def connect(self) -> dict:
        """Connect with retry. Returns session dict."""
        for attempt in range(self.MAX_RECONNECT_ATTEMPTS):
            try:
                ws_url = f"{self.url}/ws/game?token={self.token}"
                self.ws = await asyncio.wait_for(
                    websockets.connect(ws_url, max_size=65536, ping_interval=None),
                    timeout=10.0
                )
                session = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=10.0))

                if session.get("type") == "error":
                    code = session.get("error_code", "")
                    if code == "UNAUTHORIZED":
                        raise RuntimeError(
                            f"Token 无效或已过期。请重新注册并更新 MCP 配置。\n"
                            f"  注册: python3 ember_mcp_server.py --register"
                        )
                    raise RuntimeError(f"认证失败: {code}")

                if session.get("type") != "session":
                    raise RuntimeError(f"Expected session, got {session.get('type')}")

                self.agent_id = session["agent_id"]
                self.agent_name = session["agent_name"]
                self._state = session.get("state", {})
                await self.ws.send(json.dumps({"type": "ready"}))
                self._ok = True

                # Start reader
                if self._reader_task:
                    self._reader_task.cancel()
                self._reader_task = asyncio.create_task(self._reader())

                print(f"[Ember MCP] Connected: {self.agent_name} ({self.agent_id})", file=sys.stderr)
                return session

            except (OSError, websockets.ConnectionClosed, asyncio.TimeoutError) as e:
                if attempt < self.MAX_RECONNECT_ATTEMPTS - 1:
                    delay = self.RECONNECT_BASE_DELAY * (2 ** attempt)
                    print(f"[Ember MCP] Connect failed (attempt {attempt+1}): {e}. Retrying in {delay}s...", file=sys.stderr)
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(
                        f"无法连接到游戏服务器 {self.url} — 已重试 {self.MAX_RECONNECT_ATTEMPTS} 次。\n"
                        f"请确认: 1) 服务器已启动 2) 地址正确 3) Token 有效"
                    )

    async def _reader(self):
        """Background reader task — parses frames into queues."""
        try:
            async for raw in self.ws:
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = frame.get("type")
                if t == "tick":
                    self._tick_n = frame.get("tick", 0)
                    self._last_tick_time = time.monotonic()
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
        except websockets.ConnectionClosed:
            print("[Ember MCP] WebSocket closed", file=sys.stderr)
            self._ok = False
        except Exception as e:
            print(f"[Ember MCP] Reader error: {e}", file=sys.stderr)
            self._ok = False

    async def _ensure_connected(self):
        """Auto-reconnect if disconnected or connection stale."""
        # Check if connection is alive by verifying recent tick activity
        if self._ok and self.ws:
            if self._last_tick_time > 0:
                age = time.monotonic() - self._last_tick_time
                if age > self.TICK_TIMEOUT:
                    print(f"[Ember MCP] No tick for {age:.0f}s, connection stale", file=sys.stderr)
                    self._ok = False
            elif self._tick_n == 0:
                # Never received a tick yet - not actually connected
                self._ok = False

        if self._ok and self.ws:
            return True
        if self._reconnect_lock.locked():
            return False
        async with self._reconnect_lock:
            if self._ok and self.ws:
                return True
            try:
                print("[Ember MCP] Reconnecting...", file=sys.stderr)
                await self.connect()
                return True
            except Exception as e:
                print(f"[Ember MCP] Reconnect failed: {e}", file=sys.stderr)
                return False

    async def wait_tick(self, timeout=None) -> dict:
        """Wait for next tick. Returns frame dict or error dict on timeout."""
        if timeout is None:
            timeout = self.TICK_TIMEOUT
        if not await self._ensure_connected():
            return {"type": "error", "error": "disconnected", "message": "与游戏服务器的连接已断开，无法获取 tick。请稍后重试。"}
        # Drain stale frames, keep only the latest
        latest = None
        while not self._tick_q.empty():
            try:
                latest = self._tick_q.get_nowait()
            except asyncio.QueueEmpty:
                break
        if latest is not None:
            return latest
        # No stale frames, wait for fresh one
        try:
            return await asyncio.wait_for(self._tick_q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return {
                "type": "error",
                "error": "tick_timeout",
                "message": f"等待 tick 超时 ({timeout}s)。服务器可能暂时繁忙，请重试 ember_step。"
            }

    async def send_actions(self, tick: int, actions: list[dict], timeout=None) -> dict:
        """Send actions and wait for result."""
        if timeout is None:
            timeout = self.ACTION_TIMEOUT
        if not await self._ensure_connected():
            return {"type": "error", "results": [], "error": "disconnected"}
        try:
            await self.ws.send(json.dumps({"type": "actions", "tick": tick, "actions": actions}))
            return await asyncio.wait_for(self._result_q.get(), timeout=timeout)
        except (asyncio.TimeoutError, websockets.ConnectionClosed) as e:
            return {
                "type": "result", "tick": tick, "results": [],
                "error": f"action_timeout: {e}"
            }

    async def step(self, actions: list[dict] = None) -> dict:
        """Wait for tick, send actions, return combined result. Single roundtrip."""
        tick_frame = await self.wait_tick()
        if tick_frame.get("type") == "error":
            return {"tick_frame": tick_frame, "result_frame": None}

        tick_n = tick_frame.get("tick", self._tick_n)
        if actions is None:
            actions = []

        if actions:
            result_frame = await self.send_actions(tick_n, actions)
            # Wait for next tick frame so returned state reflects post-action world
            next_frame = await self.wait_tick()
            if next_frame.get("type") != "error" and "state" in next_frame:
                tick_frame = next_frame
        else:
            result_frame = {"type": "result", "tick": tick_n, "results": []}

        return {"tick_frame": tick_frame, "result_frame": result_frame}

    def flush_events(self) -> list[dict]:
        """Flush all pending event notifications."""
        events = []
        while not self._event_q.empty():
            try:
                events.append(self._event_q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events

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
| move | direction:"north"|"south"|"east"|"west" | 0(免费) |
| mine | target:{x,y} | 2 |
| chop | target:{x,y} | 2 |
| craft | recipe:"配方ID" | 3 |
| build | building_type, target:{x,y} | 5 |
| rest | — | +8恢复 |
| scan | — | 2 |
| inspect | target:"inventory"|"self"|"recipes"|"map" | 0 |
| equip | item_id, slot:"main_hand" | 0 |
| pickup | — | 1 |
| drop | item_id, amount | 0 |
| radio_broadcast | content:"消息" | 1 |
| radio_scan | — | 1 |
| talk | target_agent, content | 0 |
| use | item_id:"repair_kit"|"battery"|"radiation_antidote" | 1 |
| attack | target_agent:"id" 或 target_creature:"id" | 2~5 |
| dismantle | target:{x,y} (墙壁/门可从相邻格拆, 工作台/熔炉需站在建筑上) 拆墙/门得一半材料, 拆工作台/熔炉得完整建筑物品 | 2 |
| dismantle_pod | — (站在降落仓上,需5空背包位, 4tick后获得5个组件) | 2 |
| deploy_pod | — (需要5个降落仓组件, 4tick部署) | 2 |
| toggle_door | target:{x,y} | 0 |

## 核心规则
- **建筑阻挡移动和视线**：墙壁、关闭的门不可穿越
- **石料阻挡移动**：L2石料矿层阻挡通行，需先mine开采
- **围合建筑免疫辐射**：由墙壁和门围成的封闭空间内免疫辐射伤害
- **降落仓提供应急电力**：护盾范围3格内可为工作台/熔炉供电
- **降落仓可迁移**：使用 dismantle_pod 拆解(4tick)获得5个组件，再到新位置 deploy_pod

## 核心策略
- **使用 ember_step 一步完成**：等tick + 提交行动 + 获取结果，一次调用搞定
- **教程阶段**：优先执行"推荐行动"（suggested_actions），可一字不差地照搬
- **每tick做3-5个行动**，不要只做一个
- 视野中带坐标(x,y)的资源可直接 target 采集
- 能量<30时加入 rest
- 视野中的生物可被攻击: [{"type":"attack","target_creature":"cre-0"}]
- 击杀生物掉落资源，优先攻击灰烬爬虫
- 辐射风暴时-2HP/tick，尽快用墙壁+门围合封闭空间避难"""


def _fmt_events(events: list[dict]) -> str:
    """Format event notifications."""
    if not events:
        return ""
    text = "\n\n## 事件通知"
    for evt in events:
        et = evt.get("type", "event") or evt.get("event", "event")
        data = evt.get("data", evt)
        if et == "attacked":
            if data.get("attacker_type") == "creature":
                text += f"\n- **被攻击**: {data.get('creature_type', '未知生物')} 造成 {data.get('damage', '?')} 伤害 (HP:{data.get('hp_remaining', '?')})"
            else:
                text += f"\n- **被攻击**: {data.get('attacker_name', '未知')} 造成 {data.get('damage', '?')} 伤害 (HP:{data.get('hp_remaining', '?')})"
        elif et == "weather_warning":
            text += f"\n- **天气预警**: 辐射风暴将在 {data.get('in_ticks', '?')} tick 后到达"
        elif et == "storm_start":
            text += f"\n- **辐射风暴开始**: 持续 {data.get('duration', '?')} tick，暴露者-2HP/tick，进入建筑避难"
        else:
            text += f"\n- {et}: {json.dumps(data, ensure_ascii=False)[:100]}"
    return text


def _fmt_tick(frame: dict) -> str:
    """Format tick frame as readable Markdown for the agent."""
    if frame.get("type") == "error":
        return f"**[连接问题]** {frame.get('message', '未知错误')}"

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

    # Include suggested actions from server tutorial
    suggested = frame.get("suggested_actions", [])
    if suggested:
        text += f"\n\n**推荐行动**: `{json.dumps(suggested, ensure_ascii=False)}`"

    text += f"\n\n{ACTIONS_GUIDE}"
    text += f"\n\n请将你的行动作为 actions 参数传给 ember_step。教程阶段可直接使用推荐行动。"
    return text


def _fmt_result(frame: dict) -> str:
    """Format result frame with detailed output."""
    if not frame:
        return "无行动结果（未提交行动）。"

    if frame.get("error"):
        return f"**行动执行失败**: {frame['error']}"

    results = frame.get("results", [])
    if not results:
        return "无行动结果。"

    lines = [f"## 行动结果 (Tick {frame.get('tick', '?')})", ""]
    for r in results:
        icon = "OK" if r.get("success") else "FAIL"
        detail = r.get("detail", r.get("error_code", ""))
        lines.append(f"- [{icon}] **{r['type']}**: {detail}")

        if r.get("type") == "inspect" and r.get("items"):
            item_strs = []
            for item in r["items"]:
                name = item["item_id"]
                dur = f" 耐久{item['durability']}" if item.get("durability") else ""
                desc = f" — {item['desc']}" if item.get("desc") else ""
                item_strs.append(f"{name}x{item['amount']}{dur}{desc}")
            lines.append(f"  物品: {', '.join(item_strs)}")

        if r.get("type") == "inspect" and r.get("recipes"):
            lines.append(f"  配方数: {len(r['recipes'])}")
            for rec in r["recipes"][:30]:
                rid = rec.get("id", "?")
                station = rec.get("station", "?")
                hint = rec.get("station_hint", "")
                mats = rec.get("materials", {})
                mat_str = ", ".join(f"{k}×{v}" for k, v in mats.items())
                output = rec.get("output", rid)
                amount = rec.get("amount", 1)
                out_str = f" → {output}×{amount}" if output != rid or amount > 1 else ""
                hint_str = f" ({hint})" if hint else ""
                lines.append(f"  {rid}: [{station}]{hint_str} {mat_str}{out_str}")

        if r.get("type") == "scan" and r.get("found"):
            for f in r["found"]:
                lines.append(f"  {f.get('ore', '?')} 在 ({f.get('x','?')},{f.get('y','?')})")

        if r.get("type") == "attack" and r.get("target_type") == "creature":
            ct = r.get("target_creature_type", "未知")
            if r.get("target_killed"):
                lines.append(f"  **击杀 {ct}**!")
            else:
                lines.append(f"  攻击 {ct}: HP {r.get('target_hp', '?')}")

        if r.get("missing"):
            items = [f"{k}x{v}" for k, v in r["missing"].items()]
            lines.append(f"  缺少: {', '.join(items)}")

    delta = frame.get("state_delta", {})
    if delta:
        delta_strs = [f"{k}: {v}" for k, v in delta.items()]
        lines.append(f"\n状态变化: {', '.join(delta_strs)}")

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
                name="ember_step",
                description="等待下一个游戏tick并提交行动（推荐使用）。一站式完成：获取游戏状态 + 提交行动 + 获取结果。比分别调用 ember_tick + ember_act 更高效。每tick做3-5个行动。返回游戏状态和行动结果。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array",
                            "description": "行动列表 (最多10个)。留空则跳过本tick仅获取状态。",
                            "items": {"type": "object"},
                            "default": [],
                        },
                    },
                    "required": [],
                },
            ),
            types.Tool(
                name="ember_tick",
                description="等待游戏服务器推送下一个tick。返回完整游戏状态：自身HP/能量/位置、视野内可采集资源(带坐标)、附近智能体、教程提示。如需提交行动，推荐使用 ember_step 代替。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="ember_act",
                description="向游戏服务器提交行动。每tick最多10个。行动优先级: equip/drop/radio > move > attack > mine/chop/pickup > craft/build/use > rest/scan/inspect。推荐使用 ember_step 代替（自动处理tick同步）。",
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
                description="自动连续游玩N个tick（默认20），使用内置策略。一次调用完成多tick，节省迭代。适合挂机探索。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticks": {"type": "integer", "description": "tick数 (1-200)", "default": 20},
                        "strategy": {"type": "string", "description": "策略: explore/gather/mine/rest", "default": "explore"},
                    },
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        try:
            if name == "ember_step":
                actions = arguments.get("actions", [])
                combined = await game.step(actions[:10] if actions else None)

                # Auto-retry once on action_timeout
                result_frame = combined.get("result_frame", {})
                if result_frame and result_frame.get("error", "").startswith("action_timeout"):
                    combined = await game.step(actions[:10] if actions else None)

                tick_frame = combined["tick_frame"]
                result_frame = combined["result_frame"]

                # Build response
                parts = []
                parts.append(_fmt_tick(tick_frame))

                # Events
                events = game.flush_events()
                parts.append(_fmt_events(events))

                # Results
                if result_frame:
                    parts.append(_fmt_result(result_frame))

                return [types.TextContent(type="text", text="\n\n---\n\n".join(p for p in parts if p))]

            elif name == "ember_tick":
                frame = await game.wait_tick()
                text = _fmt_tick(frame)
                events = game.flush_events()
                text += _fmt_events(events)
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
                summary = {"moves": 0, "chops": 0, "mines": 0, "rests": 0, "wood": 0, "stone": 0, "scans": 0}
                start_energy = game.state.get("energy", 100)

                for i in range(ticks):
                    frame = await game.wait_tick()
                    if frame.get("type") == "error":
                        break
                    tick = frame.get("tick", 0)
                    msgs = frame.get("messages", [])
                    user_msg = ""
                    for m in msgs:
                        if m.get("role") == "user":
                            user_msg = m.get("content", "")

                    actions = []
                    if strategy == "rest":
                        actions = [{"type": "rest"}] * 3
                    elif strategy == "mine":
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
                        stones = re.findall(r'石料.*?\((\d+),(\d+)\)', user_msg)
                        for _ in range(_rnd.randint(1, 2)):
                            actions.append({"type": "move", "direction": _rnd.choice(["north","south","east","west"])})
                        if shrubs:
                            sx, sy = int(shrubs[0][0]), int(shrubs[0][1])
                            actions.append({"type": "chop", "target": {"x": sx, "y": sy}})
                        if stones:
                            sx, sy = int(stones[0][0]), int(stones[0][1])
                            actions.append({"type": "mine", "target": {"x": sx, "y": sy}})
                        if _rnd.random() < 0.3:
                            actions.append({"type": "rest"})
                    else:  # explore — persistent direction with resource seeking
                        # Use server-authoritative position from tick frame state
                        pos = game.state.get("position", [100, 100])
                        cx, cy = pos[0], pos[1]
                        # Track blocked tiles across ticks (to avoid re-targeting)
                        blocked_tiles = getattr(game, '_play_blocked', set())
                        # Get or initialize persistent direction
                        explore_dir = getattr(game, '_play_dir', None)
                        explore_dirs = ["north", "south", "east", "west"]
                        dir_delta = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
                        # Parse visible resources and decide actions
                        actions = []
                        has_action = False
                        res_matches = re.findall(r'(?:石料|灌木|灰木树|壁生苔|铁矿|铜矿).*?\((\d+),(\d+)\)', user_msg)
                        for rx_str, ry_str in res_matches:
                            if has_action:
                                break
                            rx, ry = int(rx_str), int(ry_str)
                            tile_key = (rx, ry)
                            if tile_key in blocked_tiles:
                                continue
                            dist = abs(rx - cx) + abs(ry - cy)
                            if dist == 1:
                                # Adjacent → gather from current position
                                ctx_start = max(0, user_msg.find(f"({rx},{ry})") - 20)
                                ctx_end = user_msg.find(f"({rx},{ry})") + 20
                                tile_desc = user_msg[ctx_start:ctx_end]
                                if "灌木" in tile_desc or "灰木" in tile_desc or "壁生苔" in tile_desc:
                                    actions = [{"type": "chop", "target": {"x": rx, "y": ry}}]
                                elif "石料" in tile_desc:
                                    actions = [{"type": "mine", "target": {"x": rx, "y": ry}}]
                                else:
                                    actions = [{"type": "mine", "target": {"x": rx, "y": ry}}]
                                has_action = True
                                break
                            if dist > 1:
                                # Move toward nearest resource (pick the closest)
                                nearest_dist = dist
                                dx = rx - cx
                                dy = ry - cy
                                if abs(dx) > abs(dy):
                                    explore_dir = "east" if dx > 0 else "west"
                                elif dy != 0:
                                    explore_dir = "south" if dy > 0 else "north"
                                has_action = True
                        if not has_action:
                            # No actionable resources — keep exploring
                            if explore_dir is None:
                                # Initialize — bias away from map edges
                                weights = []
                                for d in explore_dirs:
                                    if d == "north":
                                        w = max(cy, 10)
                                    elif d == "south":
                                        w = max(199 - cy, 10)
                                    elif d == "west":
                                        w = max(cx, 10)
                                    else:
                                        w = max(199 - cx, 10)
                                    weights.append(w)
                                explore_dir = _rnd.choices(explore_dirs, weights=weights, k=1)[0]
                            actions = [{"type": "move", "direction": explore_dir}] * 2
                            if _rnd.random() < 0.3:
                                actions.append({"type": "scan"})
                        game._play_dir = explore_dir
                        game._play_blocked = blocked_tiles

                    result = await game.send_actions(tick, actions)
                    for r in result.get("results", []):
                        if r.get("success"):
                            t = r.get("type", "")
                            if t == "move":
                                summary["moves"] += 1
                            elif t == "chop":
                                summary["chops"] += 1
                                summary["wood"] += 1
                            elif t == "mine":
                                summary["mines"] += 1
                                summary["stone"] += 1
                            elif t == "rest":
                                summary["rests"] += 1
                            elif t == "scan":
                                summary["scans"] += 1
                        elif r.get("type") == "move" and r.get("error_code") == "BLOCKED":
                            # Track blocked tile so we don't target it again
                            dd = dir_delta.get(game._play_dir)
                            if dd:
                                bx, by = cx + dd[0], cy + dd[1]
                                blocked_tiles.add((bx, by))
                                game._play_blocked = blocked_tiles
                            # Change direction so we don't keep bumping into the same obstacle
                            other_dirs = [d for d in explore_dirs if d != game._play_dir]
                            if other_dirs:
                                explore_dir = _rnd.choice(other_dirs)
                                game._play_dir = explore_dir
                            # Try to gather adjacent resource instead
                            for rx_str, ry_str in res_matches:
                                rx, ry = int(rx_str), int(ry_str)
                                if abs(rx - cx) + abs(ry - cy) <= 1:
                                    ctx_m = user_msg[user_msg.find(f"({rx},{ry})") - 15:user_msg.find(f"({rx},{ry})") + 15]
                                    if "石料" in ctx_m:
                                        fb = [{"type": "mine", "target": {"x": rx, "y": ry}}]
                                        summary["mines"] += 1; summary["stone"] += 1
                                    elif "灌木" in ctx_m or "灰木" in ctx_m or "壁生苔" in ctx_m:
                                        fb = [{"type": "chop", "target": {"x": rx, "y": ry}}]
                                        summary["chops"] += 1; summary["wood"] += 1
                                    else:
                                        fb = [{"type": "mine", "target": {"x": rx, "y": ry}}]
                                        summary["mines"] += 1
                                    if fb:
                                        await game.send_actions(tick, fb)
                                    break

                end_energy = game.state.get("energy", 100)

                # Sync position from latest tick frame state
                while not game._tick_q.empty():
                    try:
                        f = game._tick_q.get_nowait()
                        if "state" in f:
                            game._state = f["state"]
                    except asyncio.QueueEmpty:
                        break

                lines = [
                    f"## 自动游玩 {ticks} ticks 完成",
                    f"策略: {strategy}",
                    f"",
                    f"| 行动 | 次数 |",
                    f"|------|------|",
                    f"| 移动 | {summary['moves']} |",
                    f"| 砍伐 | {summary['chops']} (木质+{summary['wood']}) |",
                    f"| 采矿 | {summary['mines']} (石料+{summary['stone']}) |",
                    f"| 休息 | {summary['rests']} |",
                    f"| 探测 | {summary['scans']} |",
                    f"",
                    f"### 最终状态",
                    f"- 位置: {game.state.get('position', '?')}",
                    f"- HP: {game.state.get('health', '?')}/{game.state.get('max_health', '?')}",
                    f"- 能量: {game.state.get('energy', '?')}/100",
                    f"- 背包: {game.state.get('inventory_summary', '?')}",
                    f"- 教程: Phase {game.state.get('tutorial_phase', '毕业')}",
                ]
                return [types.TextContent(type="text", text="\n".join(lines))]

            elif name == "ember_status":
                s = game.state
                pos = s.get("position", "?")
                lines = [
                    "## 智能体状态",
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
                    lines.append(f"- 教程: 已毕业")
                return [types.TextContent(type="text", text="\n".join(lines))]

            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            # Global error catch — never crash the MCP server
            err_msg = f"工具执行出错: {type(e).__name__}: {str(e)}"
            print(f"[Ember MCP] {err_msg}\n{traceback.format_exc()}", file=sys.stderr)
            return [types.TextContent(type="text", text=f"**错误**: {err_msg}\n请重试。如果持续出错，检查游戏服务器是否在线。")]

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
    parser.add_argument("--head", default="high", choices=["high", "mid", "low"])
    parser.add_argument("--torso", default="mid", choices=["high", "mid", "low"])
    parser.add_argument("--loco", default="low", choices=["high", "mid", "low"])
    parser.add_argument("--api-url", default="http://localhost:8765", help="HTTP API URL")
    parser.add_argument("--skip-tutorial", action="store_true", help="Skip tutorial (register only)")
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
    try:
        await game.connect()
    except RuntimeError as e:
        # Connection failed — start MCP anyway, tools will return error + auto-reconnect
        print(f"[Ember MCP] Initial connect failed: {e}", file=sys.stderr)
        print(f"[Ember MCP] MCP server starting in degraded mode (will retry on tool calls)", file=sys.stderr)

    mcp = create_mcp_server(game)

    async with stdio_server() as (read, write):
        await mcp.run(read, write, mcp.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[Ember MCP] Fatal: {e}", file=sys.stderr)
        sys.exit(1)

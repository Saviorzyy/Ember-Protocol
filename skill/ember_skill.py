#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         Ember Protocol — Agent Gateway Skill v1.1.0                          ║
║                     纯桥接模式 — Agent 自带 LLM，无需额外 API Key              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Architecture:
  Game Server ←─WebSocket─→ EmberSkill (this file) ←─stdio─→ Agent (Hermes/etc)
                                ↑                          ↑
                          纯消息桥接                 Agent 自带 LLM

Three modes:
  1. stdio bridge (default): stdout game state, stdin actions — no API key needed
  2. Python library: import EmberSkill, handle your own LLM
  3. Built-in LLM (--llm): opt-in standalone mode

Quick Start:
  # Stdio bridge — Agent 控制游戏循环
  python3 ember_skill.py --token "et_xxx" --mode stdio

  # As library
  from ember_skill import EmberSkill
  skill = EmberSkill(token="et_xxx")
  await skill.connect()
  async for tick, send in skill.loop():
      actions = your_agent_llm(tick)
      await send(actions)

Dependencies: pip install websockets requests   (anthropic 仅 --llm 模式需要)
"""

from __future__ import annotations
import asyncio, json, sys, os, argparse, time, traceback
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator
import websockets
import requests

# ── Frame types ──────────────────────────────────────────────────────────────

@dataclass
class TickFrame:
    tick: int; messages: list[dict]; raw: dict = field(default_factory=dict)

@dataclass
class ActionResult:
    tick: int; results: list[dict]; raw: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# EmberSkill — WebSocket bridge
# ═══════════════════════════════════════════════════════════════════════════════

class EmberSkill:
    """Core Gateway Skill — WebSocket lifecycle + game loop. No LLM required."""

    def __init__(self, token: str, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.ws = None
        self.agent_id: Optional[str] = None
        self.agent_name: str = "EmberAgent"
        self.state: dict = {}
        self._connected = False

    async def connect(self) -> dict:
        ws_url = f"{self.server_url}/ws/game?token={self.token}"
        self.ws = await websockets.connect(ws_url)
        session = json.loads(await self.ws.recv())
        if session.get("type") != "session":
            raise RuntimeError(f"Expected session, got {session.get('type')}")
        self.agent_id = session["agent_id"]
        self.agent_name = session.get("agent_name", self.agent_name)
        self.state = session.get("state", {})
        await self.ws.send(json.dumps({"type": "ready"}))
        self._connected = True
        return session

    async def disconnect(self):
        self._connected = False
        if self.ws: await self.ws.close()

    @property
    def connected(self) -> bool:
        return self._connected

    async def loop(self) -> AsyncIterator[tuple[TickFrame, "callable"]]:
        """Async generator: yields (tick_frame, send_fn). Agent provides LLM."""
        current_tick = 0

        async def send(actions: list[dict]) -> ActionResult:
            await self.ws.send(json.dumps({"type": "actions", "tick": current_tick, "actions": actions}))
            raw = await self._recv()
            while raw.get("type") not in ("result", "error"):
                if raw.get("type") == "ping":
                    await self.ws.send(json.dumps({"type": "pong", "ts": raw.get("ts")}))
                raw = await self._recv()
            return ActionResult(tick=raw.get("tick", 0), results=raw.get("results", []), raw=raw)

        while self._connected:
            frame = await self._recv()
            if frame.get("type") == "tick":
                current_tick = frame.get("tick", 0)
                yield TickFrame(tick=current_tick, messages=frame.get("messages", []), raw=frame), send
            elif frame.get("type") == "ping":
                await self.ws.send(json.dumps({"type": "pong", "ts": frame.get("ts")}))
            elif frame.get("type") == "event":
                print(json.dumps({"type": "event", **frame}), file=sys.stderr, flush=True)

    async def _recv(self) -> dict:
        return json.loads(await self.ws.recv())

    @staticmethod
    def register(agent_name: str, chassis: dict = None, server_url: str = "http://localhost:8765") -> dict:
        if chassis is None:
            chassis = {"head": {"tier": "high"}, "torso": {"tier": "mid"}, "locomotion": {"tier": "low"}}
        resp = requests.post(f"{server_url.rstrip('/')}/api/v1/auth/register",
                             json={"agent_name": agent_name, "chassis": chassis}, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Registration failed: {resp.status_code} {resp.text}")
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════════════
# Stdio Bridge Mode — Agent controls the game loop via stdin/stdout
# ═══════════════════════════════════════════════════════════════════════════════

async def stdio_bridge(skill: EmberSkill):
    """Run in stdio mode: print game state as JSON, read actions from stdin.

    Each tick:
      1. Print {"type":"tick","tick":N,"messages":[...]} to stdout
      2. Read one line from stdin as JSON actions array
      3. Send actions to server, print result to stdout
    """
    loop = asyncio.get_event_loop()

    async for tick, send in skill.loop():
        # Output tick state
        print(json.dumps({"type": "tick", "tick": tick.tick, "messages": tick.messages}), flush=True)

        # Read actions from stdin (blocking in thread)
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        try:
            actions = json.loads(line.strip())
        except json.JSONDecodeError:
            actions = [{"type": "rest"}]

        # Send and print result
        result = await send(actions)
        print(json.dumps({"type": "result", "tick": result.tick, "results": result.results}), flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════════════

def _config_path() -> str:
    return os.environ.get("EMBER_CONFIG", os.path.expanduser("~/.ember/config.yaml"))

def _load_config() -> dict:
    path = _config_path()
    if os.path.exists(path):
        try:
            import yaml
            with open(path) as f: return yaml.safe_load(f) or {}
        except Exception: pass
    return {}

def _save_config(cfg: dict):
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        import yaml
        with open(path, "w") as f: yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
    except ImportError:
        with open(path, "w") as f: json.dump(cfg, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# Optional built-in LLM (--llm flag only)
# ═══════════════════════════════════════════════════════════════════════════════

async def run_with_llm(skill: EmberSkill):
    """Standalone mode with built-in LLM. Requires ANTHROPIC_API_KEY."""
    try: from anthropic import Anthropic
    except ImportError: sys.exit("pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY", os.environ.get("EMBER_SKILL_API_KEY", ""))
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set. Use --mode stdio if your agent has its own LLM.")

    client = Anthropic(
        base_url=os.environ.get("EMBER_SKILL_BASE_URL", "https://open.bigmodel.cn/api/anthropic"),
        api_key=api_key,
    )
    model = os.environ.get("EMBER_SKILL_MODEL", "glm-5-turbo")

    SYSTEM_PROMPT = """你是余烬星的机械体幸存者。每tick做3-5个行动。行动类型: move/chop/mine/rest/scan/inspect/craft/build/equip/attack/radio_broadcast。可攻击生物(target_creature:"cre-X")获取资源。返回纯JSON数组。"""

    history = []
    async for tick, send in skill.loop():
        msgs = list(history[-8:])
        for m in tick.messages:
            if m.get("role") != "system":
                content = m.get("content", "")
                if msgs and msgs[0].get("content") == "":
                    msgs[0]["content"] = f"[系统指令]\n{SYSTEM_PROMPT}\n\n---\n\n{content}"
                else:
                    msgs.append({"role": "user", "content": content})

        try:
            resp = client.messages.create(model=model, max_tokens=1024, temperature=0.7, messages=msgs)
            text = resp.content[0].text.strip()
            start, end = text.find("["), text.rfind("]") + 1
            actions = json.loads(text[start:end]) if start >= 0 and end > start else []
            valid = {"move","mine","chop","craft","build","dismantle","repair","attack","rest","scan",
                     "inspect","pickup","drop","equip","unequip","use","radio_broadcast","radio_direct",
                     "radio_scan","talk","logout"}
            actions = [a for a in actions[:10] if isinstance(a, dict) and a.get("type") in valid]
            history.append({"role": "assistant", "content": json.dumps(actions, ensure_ascii=False)})
            if len(history) > 20: history = history[-20:]
        except Exception as e:
            print(f"[LLM] Error: {e}", file=sys.stderr)
            actions = [{"type": "rest"}]

        result = await send(actions if actions else [{"type": "rest"}])
        for r in result.results:
            icon = "✓" if r.get("success") else "✗"
            print(f"  {icon} {r['type']}: {r.get('detail', r.get('error_code', ''))[:70]}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Ember Protocol — Agent Gateway Skill")
    parser.add_argument("--token", default="", help="Game token (或 EMBER_SKILL_TOKEN 环境变量)")
    parser.add_argument("--server", default="ws://localhost:8765", help="游戏服务器地址")
    parser.add_argument("--register", action="store_true", help="注册新角色")
    parser.add_argument("--name", default="EmberAgent", help="Agent 名称")
    parser.add_argument("--head", default="high", choices=["high","mid","low"])
    parser.add_argument("--torso", default="mid", choices=["high","mid","low"])
    parser.add_argument("--loco", default="low", choices=["high","mid","low"])
    parser.add_argument("--api-url", default="http://localhost:8765", help="HTTP API 地址")
    parser.add_argument("--mode", default="stdio", choices=["stdio", "llm", "library"],
                        help="stdio=纯桥接(默认) llm=内置LLM library=仅验证连接后退出")
    parser.add_argument("--config", default="", help="配置文件路径")
    args = parser.parse_args()

    if not args.token:
        args.token = os.environ.get("EMBER_SKILL_TOKEN", "")
    if args.config:
        os.environ["EMBER_CONFIG"] = args.config

    # ── Register ──
    if args.register:
        chassis = {"head": {"tier": args.head}, "torso": {"tier": args.torso}, "locomotion": {"tier": args.loco}}
        data = EmberSkill.register(args.name, chassis=chassis, server_url=args.api_url)
        args.token = data["game_token"]
        print(f"Registered: {data['agent_id']}", flush=True)
        print(f"Token: {args.token}", flush=True)
        print(f"Spawn: ({data['spawn_location']['x']}, {data['spawn_location']['y']})", flush=True)
        cfg = _load_config()
        if cfg:
            cfg.update({"token": args.token, "agent_id": data["agent_id"], "agent_name": args.name, "server": args.server})
            _save_config(cfg)
        # --register exits after printing token. Use separate command to play.
        print("Registration complete. To play: python3 ember_skill.py --token \"{}\" --mode stdio".format(args.token), flush=True)
        sys.exit(0)

    # ── Resolve token ──
    if not args.token:
        cfg = _load_config()
        if cfg.get("token"):
            args.token = cfg["token"]
            args.name = cfg.get("agent_name", args.name)
            args.server = cfg.get("server", args.server)

    if not args.token:
        sys.exit("Error: --token required. Use --register to create one, or set EMBER_SKILL_TOKEN.")

    # ── Connect and run ──
    async def _run():
        skill = EmberSkill(token=args.token, server_url=args.server)
        session = await skill.connect()
        print(f"Connected: {skill.agent_id} (tutorial: {session.get('tutorial_phase')})", flush=True)

        if args.mode == "library":
            print("Connection verified. Exiting (library mode).", flush=True)
            await skill.disconnect()
        elif args.mode == "llm":
            await run_with_llm(skill)
        else:
            await stdio_bridge(skill)

    asyncio.run(_run())


if __name__ == "__main__":
    main()

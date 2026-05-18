"""Ember Protocol — WebSocket Handler"""
from __future__ import annotations
import json
import asyncio
import time
from aiohttp import web, WSMsgType
from .world import World
from .config import *


class WSManager:
    """Manages WebSocket connections and message routing.

    Uses per-connection queue + writer task pattern to ensure
    single-writer access to each WebSocket connection.
    """

    def __init__(self, world: World):
        self.world = world
        self.connections: dict[str, web.WebSocketResponse] = {}
        self.send_queues: dict[str, asyncio.Queue] = {}
        self.writer_tasks: dict[str, asyncio.Task] = {}
        self.connect_time: dict[str, float] = {}
        # W-5: Heartbeat tracking
        self.last_pong: dict[str, float] = {}  # agent_id -> last pong timestamp
        self.missed_heartbeats: dict[str, int] = {}  # agent_id -> missed count
        # W-6: Reconnection window tracking
        self.disconnected_agents: dict[str, dict] = {}  # agent_id -> {disconnect_time, token_hash}

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle a new WebSocket connection."""
        ws = web.WebSocketResponse(max_msg_size=65536)
        await ws.prepare(request)

        token = request.query.get("token", "")
        if not token:
            await ws.send_json({"type": "error", "error_code": "UNAUTHORIZED", "detail": "缺少 game_token"})
            await ws.close()
            return ws

        agent_id = None
        for aid, th in self.world.token_hashes.items():
            import hashlib
            if th == hashlib.sha256(token.encode()).hexdigest():
                agent_id = aid
                break

        if not agent_id or agent_id not in self.world.agents:
            await ws.send_json({"type": "error", "error_code": "UNAUTHORIZED", "detail": "无效的 game_token"})
            await ws.close()
            return ws

        agent = self.world.agents[agent_id]
        agent.online = True
        self.connections[agent_id] = ws
        self.connect_time[agent_id] = time.time()

        # Create send queue and writer task
        queue: asyncio.Queue = asyncio.Queue()
        self.send_queues[agent_id] = queue

        async def writer():
            """Dedicated writer task - single writer per WS connection."""
            while True:
                data = await queue.get()
                if data is None:  # Sentinel to stop
                    break
                if not ws.closed:
                    try:
                        await ws.send_json(data)
                    except Exception as e:
                        print(f"  [WS] Write error for {agent_id[:12]}: {e}")
                        break

        writer_task = asyncio.create_task(writer())
        self.writer_tasks[agent_id] = writer_task

        # W-5: Initialize heartbeat tracking
        self.last_pong[agent_id] = time.time()
        self.missed_heartbeats[agent_id] = 0

        # Send session frame via queue
        await queue.put(self._build_session_frame(agent))

        # Message reader loop
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(agent_id, msg.data, queue)
                elif msg.type == WSMsgType.ERROR:
                    print(f"WS error from {agent_id[:12]}: {ws.exception()}")
        except Exception as e:
            print(f"WS connection error for {agent_id[:12]}: {e}")
        finally:
            agent.online = False
            # W-6: Track for reconnection window
            self.disconnected_agents[agent_id] = {
                "disconnect_time": time.time(),
                "token_hash": self.world.token_hashes.get(agent_id),
            }
            await queue.put(None)  # Stop writer
            writer_task.cancel()
            self.connections.pop(agent_id, None)
            self.send_queues.pop(agent_id, None)
            # W-5: Clean up heartbeat tracking
            self.last_pong.pop(agent_id, None)
            self.missed_heartbeats.pop(agent_id, None)
            print(f"Agent {agent_id[:12]} disconnected")

        return ws

    def _build_session_frame(self, agent) -> dict:
        return {
            "type": "session",
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "tutorial_phase": agent.tutorial_phase,
            "state": self.world._agent_state_dict(agent),
        }

    async def _handle_message(self, agent_id: str, raw: str, queue: asyncio.Queue):
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            await queue.put({"type": "error", "error_code": "MALFORMED_FRAME", "detail": "无法解析为 JSON"})
            return

        msg_type = frame.get("type")
        if msg_type == "ready":
            agent = self.world.agents.get(agent_id)
            if agent:
                agent.online = True
                # Auto-graduate tutorial after first inspect
                # Tutorial phases: 0=苏醒, 1=部署, 2=合成, 3=建造, 4=通信
                # For MVP demo, graduate after phase 0 (first inspect)
        elif msg_type == "actions":
            tick = frame.get("tick")
            actions = frame.get("actions", [])
            if tick is None:
                await queue.put({"type": "error", "error_code": "MALFORMED_ACTIONS", "detail": "actions 帧缺少必填字段 tick"})
                return
            # PRD §6.4: STALE_TICK — reject actions from a past tick
            if tick < self.world.tick_number:
                await queue.put({"type": "error", "error_code": "STALE_TICK",
                                 "detail": f"收到的 tick {tick} 已过期，当前世界 tick {self.world.tick_number}"})
                return
            # Settle actions immediately
            agent = self.world.agents.get(agent_id)
            if agent and not agent.is_dead():
                actions = actions[:MAX_ACTIONS_PER_TICK]
                # Enforce talk/broadcast/attack limits
                talk_count = 0
                broadcast_count = 0
                attack_count = 0
                filtered = []
                for a in actions:
                    at = a.get("type", "")
                    if at == "talk":
                        talk_count += 1
                        if talk_count > MAX_TALK_PER_TICK: continue
                    if at == "radio_broadcast":
                        broadcast_count += 1
                        if broadcast_count > MAX_BROADCAST_PER_TICK: continue
                    if at == "attack":
                        attack_count += 1
                        if attack_count > 1:
                            continue
                    filtered.append(a)
                results = self.world.settle_actions(self.world.tick_number, {agent_id: filtered})
                agent_results = results.get(agent_id, [])

                # Tutorial progression (PRD §4.3)
                if agent.tutorial_phase is not None:
                    phase = agent.tutorial_phase
                    progressed = False

                    if phase == 0:
                        # Phase 0: 苏醒 — inspect(inventory) to see initial items
                        for r in agent_results:
                            if r.get("type") == "inspect" and r.get("success"):
                                agent.tutorial_phase = 1
                                progressed = True
                                break

                    elif phase == 1:
                        # Phase 1: 走出降落仓护盾 — must build to graduate
                        has_build = any(r.get("type") == "build" and r.get("success") for r in agent_results)
                        if has_build:
                            agent.tutorial_phase = 2
                            progressed = True

                    elif phase == 2:
                        # Phase 2: 建造与合成 — must craft something
                        has_craft = any(r.get("type") == "craft" and r.get("success") for r in agent_results)
                        if has_craft:
                            agent.tutorial_phase = 3
                            progressed = True

                    elif phase == 3:
                        # Phase 3: 建造与庇护 — must build wall or door
                        has_build_wall = any(r.get("type") == "build" and r.get("success") for r in agent_results)
                        if has_build_wall:
                            agent.tutorial_phase = 4
                            progressed = True

                    elif phase == 4:
                        # Phase 4: 通信与生存 — radio_broadcast or talk or rest
                        has_radio = any(r.get("type") in ("radio_broadcast", "radio_direct") and r.get("success") for r in agent_results)
                        has_talk = any(r.get("type") == "talk" and r.get("success") for r in agent_results)
                        if has_radio or has_talk:
                            agent.tutorial_phase = None  # Graduate!
                            progressed = True

                    if progressed:
                        # Notify agent of phase transition
                        phase_names = {0: "苏醒", 1: "部署与采集", 2: "建造与合成", 3: "建造与庇护", 4: "通信与生存"}
                        old_name = phase_names.get(phase, f"Phase {phase}")
                        new_name = "自由模式(毕业!)" if agent.tutorial_phase is None else phase_names.get(agent.tutorial_phase, f"Phase {agent.tutorial_phase}")
                        await queue.put({"type": "event", "event": "tutorial_progress",
                            "data": {"from_phase": phase, "to_phase": agent.tutorial_phase,
                                     "message": f"✓ 教程阶段完成: {old_name} → {new_name}"}})

                    if not progressed:
                        agent.tutorial_skip_count += 1
                        if agent.tutorial_skip_count >= TUTORIAL_MAX_SKIPS:
                            agent.tutorial_phase = None  # Auto-graduate after 3 skips
                    else:
                        agent.tutorial_skip_count = 0

                # Push result through queue
                await queue.put({"type": "result", "tick": tick, "results": agent_results})
            else:
                await queue.put({"type": "error", "error_code": "AGENT_DEAD", "detail": "智能体已死亡或未就绪"})
        elif msg_type == "pong":
            # W-5: Update heartbeat tracking
            self.last_pong[agent_id] = time.time()
            self.missed_heartbeats[agent_id] = 0
        elif msg_type == "error":
            pass  # agent notification
        else:
            await queue.put({"type": "error", "error_code": "INVALID_ACTION_TYPE", "detail": f"未知帧类型: {msg_type}"})

    async def check_heartbeats(self):
        """W-5: Send pings and check for missed heartbeats."""
        now = time.time()
        to_disconnect = []
        for agent_id in list(self.connections.keys()):
            if agent_id not in self.last_pong:
                continue
            elapsed = now - self.last_pong.get(agent_id, now)
            if elapsed >= HEARTBEAT_INTERVAL:
                missed = self.missed_heartbeats.get(agent_id, 0) + 1
                self.missed_heartbeats[agent_id] = missed
                if missed >= HEARTBEAT_MAX_MISS:
                    to_disconnect.append(agent_id)
                else:
                    # Send ping
                    queue = self.send_queues.get(agent_id)
                    if queue:
                        await queue.put({"type": "ping"})
        for agent_id in to_disconnect:
            ws = self.connections.get(agent_id)
            if ws and not ws.closed:
                await ws.close(code=4000, message=b"Heartbeat timeout")

    async def cleanup_disconnected(self):
        """W-6: Remove agents whose reconnection window has expired."""
        from .models import ActionStatus
        now = time.time()
        expired = []
        for agent_id, info in list(self.disconnected_agents.items()):
            if now - info["disconnect_time"] > DISCONNECT_WINDOW:
                expired.append(agent_id)
        for agent_id in expired:
            self.disconnected_agents.pop(agent_id, None)
            # Cancel ongoing actions and clear state
            agent = self.world.agents.get(agent_id)
            if agent:
                # Cancel ongoing actions
                if agent.status in (ActionStatus.MOVING, ActionStatus.CRAFTING):
                    agent.status = ActionStatus.IDLE
                    agent.action_data = {}
                    agent.action_remaining = 0
                    agent.action_target = None
                # Note: we keep the agent in world for now (their drop pod etc persists)

    async def broadcast_tick(self, tick_frame: dict):
        """Queue tick frame for all connected agents."""
        for agent_id, queue in list(self.send_queues.items()):
            await queue.put(tick_frame)

    async def send_event(self, agent_id: str, event_type: str, data: dict):
        """Queue event frame for an agent."""
        queue = self.send_queues.get(agent_id)
        if queue:
            await queue.put({"type": "event", "event": event_type, "data": data})

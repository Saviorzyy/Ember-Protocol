"""Ember Protocol — Game Server Main Entry Point"""
from __future__ import annotations
import asyncio
import json
import os
import sqlite3
import time
import sys
from aiohttp import web
import aiohttp_cors

from .world import World
from .models import ActionStatus, InventoryItem, Position
from .ws_handler import WSManager
from .http_routes import handle_register, handle_status, handle_map_data, handle_agents_list, handle_agent_detail, handle_actions_log, handle_events, handle_rotate_token
from .sse_handler import SSEManager, handle_sse_stream
from .db import init_db, save_snapshot, load_latest_snapshot, read_wal_after, truncate_wal
from .config import MAP_SEED, TICK_INTERVAL, TICK_CADENCE, HEARTBEAT_INTERVAL, HEARTBEAT_MAX_MISS, STORM_WARNING_TICKS, HP_DROP_POD_SHIELD_REGEN


class GameServer:
    """Main game server orchestrating tick loop, WebSocket, and HTTP."""

    def __init__(self, data_dir: str = "data", seed: int = MAP_SEED):
        self.data_dir = data_dir
        self.world = World(seed=seed)
        self.ws_manager = WSManager(self.world)
        self.sse_manager = SSEManager()
        self._running = False
        self._tick = 0

        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "ember.db")
        init_db(db_path)

        # P-5: Load latest snapshot on startup for crash recovery
        snapshot = load_latest_snapshot()
        if snapshot:
            tick, data = snapshot
            self._tick = tick + 1
            # Clear WAL entries at or after snapshot tick to prevent UNIQUE conflicts
            truncate_wal(tick)
            print(f"Loaded snapshot from tick {tick}, WAL cleaned")

        # Register token hashes from DB
        conn = sqlite3.connect(db_path)
        for row in conn.execute("SELECT agent_id, token_hash FROM agents").fetchall():
            self.world.token_hashes[row[0]] = row[1]
        conn.close()

        # Restore agent state from snapshot (if any)
        if snapshot:
            data = snapshot[1]
            if "agents" in data:
                restored_count = 0
                for aid, agent_data in data["agents"].items():
                    agent = self.world.agents.get(aid)
                    if not agent:
                        continue
                    if "position" in agent_data:
                        agent.position = Position(*agent_data["position"])
                    if "health" in agent_data:
                        agent.health = agent_data["health"]
                    if "energy" in agent_data:
                        agent.energy = agent_data["energy"]
                    if "inventory" in agent_data:
                        agent.inventory = [
                            InventoryItem(**item) for item in agent_data["inventory"]
                        ]
                    if "equipment" in agent_data:
                        eq = agent_data["equipment"]
                        agent.equipment.main_hand = eq.get("main_hand")
                        agent.equipment.off_hand = eq.get("off_hand")
                        agent.equipment.armor = eq.get("armor")
                    if "backup_count" in agent_data:
                        agent.backup_count = agent_data["backup_count"]
                    if "radiation_debuff" in agent_data:
                        agent.radiation_debuff = agent_data["radiation_debuff"]
                    if "drop_pod_pos" in agent_data and agent_data["drop_pod_pos"]:
                        agent.drop_pod_pos = Position(*agent_data["drop_pod_pos"])
                    if "drop_pod_deployed" in agent_data:
                        agent.drop_pod_deployed = agent_data["drop_pod_deployed"]
                    if "tutorial_skip_count" in agent_data:
                        agent.tutorial_skip_count = agent_data["tutorial_skip_count"]
                    if "creature_kills" in agent_data:
                        agent.creature_kills = agent_data["creature_kills"]
                    restored_count += 1
                if restored_count:
                    print(f"Restored {restored_count} agent(s) from snapshot")

    async def start(self, host: str = "0.0.0.0", port: int = 8765):
        """Start the game server."""
        app = web.Application()
        app["world"] = self.world
        app["sse_manager"] = self.sse_manager

        # CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True, expose_headers="*", allow_headers="*",
            )
        })

        # HTTP routes
        app.router.add_post("/api/v1/auth/register", handle_register)
        app.router.add_get("/api/v1/status", handle_status)
        app.router.add_get("/api/v1/map", handle_map_data)
        app.router.add_get("/api/v1/agents", handle_agents_list)
        app.router.add_get("/api/v1/agents/{agent_id}", handle_agent_detail)
        app.router.add_get("/api/v1/actions", handle_actions_log)
        app.router.add_get("/api/v1/events", handle_events)
        app.router.add_get("/api/v1/events/stream", handle_sse_stream)
        app.router.add_post("/api/v1/auth/rotate-token", handle_rotate_token)

        # WebSocket route
        app.router.add_get("/ws/game", self.ws_manager.handle_connection)

        # CORS on all routes
        for route in list(app.router.routes()):
            cors.add(route)

        self._running = True

        # Start tick loop in background
        asyncio.create_task(self._tick_loop())
        # Heartbeat loop
        asyncio.create_task(self._heartbeat_loop())
        # Snapshot loop
        asyncio.create_task(self._snapshot_loop())

        print(f"🔥 余烬协议 (Ember Protocol) — Game Server")
        print(f"   Map: 200×200 | Seed: {MAP_SEED}")
        print(f"   HTTP: http://{host}:{port}")
        print(f"   WS: ws://{host}:{port}/ws/game")
        print(f"   Tick: {TICK_INTERVAL}s")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def _tick_loop(self):
        """Main tick loop with crash recovery."""
        while self._running:
            tick_start = time.monotonic()
            try:
                # Start tick
                self.world.start_tick(self._tick)

                # Build and broadcast per-agent tick frames
                for agent_id, ws_conn in list(self.ws_manager.connections.items()):
                    tick_frame = self.build_tick_for_agent(agent_id)
                    queue = self.ws_manager.send_queues.get(agent_id)
                    if queue:
                        await queue.put(tick_frame)

                # Wait for collection window
                await asyncio.sleep(TICK_INTERVAL)

                # Actions are now settled immediately in ws_handler
                # Just advance the world state
                self.world.advance_world()

                # P-1: Write WAL entries for this tick
                if self.world.changes:
                    from .db import write_wal_entries
                    write_wal_entries(self._tick, self.world.changes)

                # Flush tick notifications to connected agents
                for aid, notifs in list(self.world.tick_notifications.items()):
                    for notif in notifs:
                        await self.ws_manager.send_event(aid, notif.get("type", "event"), notif)

                # Broadcast SSE events to web frontend subscribers
                try:
                    await self.sse_manager.broadcast_tick(self.world)
                except Exception as e:
                    print(f"  [SSE ERROR] tick {self._tick}: {e}")

            except Exception as e:
                print(f"  [TICK ERROR] tick {self._tick}: {e}")
                import traceback
                traceback.print_exc()
                # Continue tick loop — don't let one error kill the game

            # Maintain cadence
            elapsed = time.monotonic() - tick_start
            remaining = TICK_CADENCE - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

            self._tick += 1

    def _build_tick_frame(self) -> dict:
        """Build a tick frame with full game state (PRD section 6.4.2)."""
        cycle_tick = self._tick % 900
        day_phase = self.world.day_phase.value
        if day_phase == "day":
            time_info = f"白天 距夜晚还有{420 - cycle_tick} tick"
        elif day_phase == "dusk":
            time_info = "黄昏"
        elif day_phase == "night":
            time_info = f"夜晚 距黎明还有{870 - cycle_tick} tick"
        else:
            time_info = "黎明"

        weather_info = "正常"
        if self.world.weather.value == "radiation_storm":
            weather_info = f"辐射风暴 (剩余{self.world.weather_remaining} tick)"

        system_msg = f"[余烬协议] 游戏状态 — Tick {self._tick} | {time_info} | {weather_info}"

        # Build per-agent user messages (done in broadcast)
        return {
            "type": "tick",
            "tick": self._tick,
            "messages": [
                {"role": "system", "content": system_msg},
            ]
        }

    def build_tick_for_agent(self, agent_id: str) -> dict:
        """Build a tick frame with full game state for a specific agent."""
        agent = self.world.agents.get(agent_id)
        if not agent:
            return {"type": "tick", "tick": self.world.tick_number, "messages": [
                {"role": "system", "content": "Agent not found"}
            ]}

        cycle_tick = self.world.tick_number % 900
        day_phase = self.world.day_phase.value
        if day_phase == "day":
            time_info = f"白天 距夜晚还有{420 - cycle_tick} tick"
        elif day_phase == "dusk":
            time_info = "黄昏"
        elif day_phase == "night":
            time_info = f"夜晚 距黎明还有{870 - cycle_tick} tick"
        else:
            time_info = "黎明"

        weather_info = "正常"
        if self.world.weather.value == "radiation_storm":
            weather_info = f"辐射风暴 (剩余{self.world.weather_remaining} tick)"

        system_msg = f"[余烬协议] 游戏状态 — Tick {self.world.tick_number} | {time_info} | {weather_info}"
        user_msg, suggested_actions = self._build_user_message(agent_id)

        # Include real-time state snapshot
        state_snapshot = {
            "position": [agent.position.x, agent.position.y],
            "health": agent.health, "max_health": agent.max_health,
            "energy": agent.energy, "max_energy": agent.max_energy,
            "held_item": agent.equipment.main_hand or "空手",
            "backup_count": agent.backup_count,
            "tutorial_phase": agent.tutorial_phase,
            "inventory_summary": self.world._inventory_summary(agent),
            "attributes": {"PER": agent.perception, "CON": agent.constitution, "AGI": agent.agility},
            "weather": self.world.weather.value,
            "weather_remaining": self.world.weather_remaining if self.world.weather.value == "radiation_storm" else 0,
            "weather_warning": self.world.weather_warning_sent,
            "weather_warning_countdown": getattr(self.world, 'weather_warning_countdown', 0),
            "radiation_debuff": agent.radiation_debuff,
        }

        # Crafting progress
        if agent.status == ActionStatus.CRAFTING and agent.action_data:
            recipe_id = agent.action_data.get("recipe", "")
            recipe_def = agent.action_data.get("recipe_def", {})
            total_ticks = recipe_def.get("ticks", 0)
            remaining = agent.action_remaining
            state_snapshot["crafting"] = {
                "recipe": recipe_id,
                "total_ticks": total_ticks,
                "remaining_ticks": remaining,
                "progress": f"{total_ticks - remaining}/{total_ticks}" if total_ticks > 0 else "instant",
            }

        return {
            "type": "tick",
            "tick": self.world.tick_number,
            "state": state_snapshot,
            "suggested_actions": suggested_actions,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]
        }

    def _build_user_message(self, agent_id: str) -> str:
        """Build the detailed game state user message for an agent."""
        agent = self.world.agents.get(agent_id)
        if not agent:
            return "=== 游戏状态 ===\n智能体未找到。", []

        world = self.world
        lines = ["=== 游戏状态 ===", ""]

        # Agent state
        pos = agent.position
        held = agent.equipment.main_hand or "空手"
        lines.append(f"【自身状态】位置:({pos.x},{pos.y}) HP:{agent.health}/{agent.max_health} 能量:{agent.energy} 手持:{held}")
        lines.append(f"  PER:{agent.perception} CON:{agent.constitution} AGI:{agent.agility} | "
                     f"视野:{agent.view_range(world.day_phase, world.weather)}格 移速:{agent.move_speed()}格/tick")

        # Show crafting progress if active
        if agent.status == ActionStatus.CRAFTING and agent.action_data:
            recipe_id = agent.action_data.get("recipe", "unknown")
            remaining = agent.action_remaining
            recipe_def = agent.action_data.get("recipe_def", {})
            total = recipe_def.get("ticks", 0)
            lines.append(f"  合成中: {recipe_id} (进度 {total - remaining}/{total}, 还需{remaining}tick)")
        lines.append(f"  备份机体:{agent.backup_count}")

        # Show drop pod power info
        if agent.drop_pod_pos and agent.drop_pod_deployed:
            pod_dist = agent.position.dist(agent.drop_pod_pos)
            from .config import DROP_POD_SHIELD_RANGE, POWER_CRAFT_COST, CENTER_Y
            # Find drop pod power node
            pod_id = f"pod-{agent.agent_id}"
            pod_power = world.power_nodes.get(pod_id)
            if pod_power:
                power_status = f"电量:{pod_power.stored}/{pod_power.capacity}"
                if pod_dist <= DROP_POD_SHIELD_RANGE:
                    lines.append(f"  降落仓电力: {power_status} (你距降落仓{pod_dist}格，在供电范围内，可为工作台/熔炉供电)")
                else:
                    lines.append(f"  降落仓电力: {power_status} (距降落仓{pod_dist}格，需在{DROP_POD_SHIELD_RANGE}格内才能使用电力)")
            else:
                lines.append(f"  降落仓距你:{pod_dist}格")

        # Tutorial guidance with precise JSON action examples
        tp = agent.tutorial_phase
        suggested_actions = []
        if tp == 0:
            lines.append(f"\n**[教程 Phase 0: 苏醒]**")
            lines.append(f"  你在降落仓中苏醒，背包里有工作台和熔炉。")
            lines.append(f"  精确行动: `[{{\"type\":\"inspect\",\"target\":\"inventory\"}}]`")
            suggested_actions = [{"type": "inspect", "target": "inventory"}]
        elif tp == 1:
            px, py = pos.x, pos.y
            lines.append(f"\n**[教程 Phase 1: 部署与采集]**")
            lines.append(f"  ⚠ 重要: 工作台和熔炉必须建在你**当前所在格** (dist=0), 不是相邻格！")
            lines.append(f"  先往一个方向走4步离开护盾范围，然后: [{{\"type\":\"build\",\"building_type\":\"workbench\",\"target\":{{\"x\":{px+4},\"y\":{py}}}}}, {{\"type\":\"build\",\"building_type\":\"furnace\",\"target\":{{\"x\":{px+4},\"y\":{py}}}}}]")
            suggested_actions = [
                {"type": "move", "direction": "east"},
                {"type": "move", "direction": "east"},
                {"type": "move", "direction": "east"},
                {"type": "move", "direction": "east"},
            ]
        elif tp == 2:
            px, py = pos.x, pos.y
            lines.append(f"\n**[教程 Phase 2: 建造与合成]**")
            lines.append(f"  在当前格部署工作台和熔炉（背包成品直接放置），然后采集石料合成工具。")
            lines.append(f"  建造: [{{\"type\":\"build\",\"building_type\":\"workbench\",\"target\":{{\"x\":{px},\"y\":{py}}}}}, {{\"type\":\"build\",\"building_type\":\"furnace\",\"target\":{{\"x\":{px},\"y\":{py}}}}}]")
            lines.append(f"  然后采集附近石料，合成 basic_excavator。")
            suggested_actions = [
                {"type": "build", "building_type": "workbench", "target": {"x": px, "y": py}},
                {"type": "build", "building_type": "furnace", "target": {"x": px, "y": py}},
                {"type": "mine", "target": {"x": px+1, "y": py}},
                {"type": "scan"},
            ]
        elif tp == 3:
            px, py = pos.x, pos.y
            has_stone = self.world.has_item(agent, "stone", 3)
            lines.append(f"\n**[教程 Phase 3: 建造与庇护]**")
            lines.append(f"  辐射风暴即将来临！用墙壁和门围合封闭空间免疫辐射。")
            if has_stone:
                lines.append(f"  精确行动: 合成 building_block×2 , 建墙+门。")
                suggested_actions = [
                    {"type": "craft", "recipe": "building_block"},
                    {"type": "craft", "recipe": "building_block"},
                    {"type": "build", "building_type": "wall", "target": {"x": px+1, "y": py}},
                    {"type": "build", "building_type": "door", "target": {"x": px-1, "y": py}},
                ]
            else:
                lines.append(f"  石料不足，先采集石料再合成 building_block。")
                suggested_actions = [
                    {"type": "mine", "target": {"x": px+1, "y": py}},
                    {"type": "mine", "target": {"x": px+1, "y": py}},
                    {"type": "craft", "recipe": "building_block"},
                    {"type": "build", "building_type": "wall", "target": {"x": px+1, "y": py}},
                ]
        elif tp == 4:
            lines.append(f"\n**[教程 Phase 4: 通信与生存]**")
            lines.append(f"  发送一次广播完成教程毕业。")
            lines.append(f"  精确行动: `[{{\"type\":\"radio_broadcast\",\"content\":\"hello world\"}}]`")
            suggested_actions = [{"type": "radio_broadcast", "content": "hello ember"}]
        elif tp is None:
            lines.append(f"\n**[自由模式]** 已毕业，自主探索生存")

        # Vicinity
        view_range = agent.view_range(world.day_phase, world.weather)
        px, py = pos.x, pos.y
        terrain_seen = []
        structures_seen = []
        agents_seen = []
        ground_seen = []
        ore_seen = []

        for dy in range(-view_range, view_range + 1):
            for dx in range(-view_range, view_range + 1):
                x, y = px + dx, py + dy
                if not world.in_bounds(x, y):
                    continue
                if abs(dx) + abs(dy) > view_range:
                    continue
                tile = world.get_tile(x, y)
                if not tile:
                    continue

                # Terrain
                tnames = {"flat": "平地", "sand": "沙地", "rock": "基岩(可通行)", "water": "水域", "trench": "沟壑"}
                if tile.l2_type == 'stone' and tile.stone_amount > 0:
                    ore_label = ""
                    if tile.ore_type and tile.ore_exposed:
                        ore_names = {"copper": "铜", "iron": "铁", "uranium": "铀", "gold": "金"}
                        ore_label = f"(含{ore_names.get(tile.ore_type, tile.ore_type)}矿脉)"
                    terrain_seen.append(f"石料{ore_label}×{tile.stone_amount}({x},{y})")
                elif tile.veg_type:
                    vnames = {"ashbush": "余烬灌木", "greytree": "灰木树", "wallmoss": "壁生苔", "rubble": "碎石堆"}
                    terrain_seen.append(f"{vnames.get(tile.veg_type, tile.veg_type)}({x},{y})")
                else:
                    terrain_seen.append(f"{tnames.get(tile.l1.value, tile.l1.value)}({x},{y})")

                # Structures
                if tile.structure:
                    structures_seen.append(f"{tile.structure.building_type.value}({x},{y}) HP:{tile.structure.hp}")

                # Ground items
                ground = world.ground_items.get((x, y))
                if ground and ground.items:
                    item_str = ", ".join(f"{i}×{a}" for i, a in ground.items)
                    ground_seen.append(f"{item_str}({x},{y})")

        # Other agents in view
        for aid, other in world.agents.items():
            if aid != agent_id and other.online and not other.is_dead():
                d = agent.position.dist(other.position)
                if d <= view_range:
                    other_held = other.equipment.main_hand or "空手"
                    agents_seen.append(f"{other.agent_name}({other.position.x},{other.position.y} 手持:{other_held} HP:{other.health})")

        # Creatures in view
        creatures_seen = []
        for cid, creature in world.creatures.items():
            d = agent.position.dist(creature.position)
            if d <= view_range:
                from .config import CREATURE_DROPS
                drops = CREATURE_DROPS.get(creature.creature_type, {})
                drop_str = ""
                if "primary" in drops:
                    drop_str = f" 掉落:{drops['primary'][0]}"
                creatures_seen.append(f"{creature.creature_type}[{creature.creature_id}]({creature.position.x},{creature.position.y} HP:{creature.hp}/{creature.max_hp}{drop_str})")
        if creatures_seen:
            lines.append(f"  生物: {', '.join(creatures_seen)}")

        lines.append(f"\n【视野】{world.day_phase.value}{' 视野'+str(view_range)+'格'}")
        if terrain_seen:
            # Prioritize: show actionable resources first
            resources = [t for t in terrain_seen if '石料' in t or '灌木' in t or '灰木树' in t or '壁生苔' in t or '碎石' in t]
            other = [t for t in terrain_seen if t not in resources]
            if resources:
                # Sort by distance (extract coords from resource strings like "石料×5(92,93)")
                import re
                def _res_dist(r):
                    m = re.search(r'\((\d+),(\d+)\)', r)
                    if m:
                        rx, ry = int(m.group(1)), int(m.group(2))
                        return abs(rx - pos.x) + abs(ry - pos.y)
                    return 999
                resources.sort(key=_res_dist)
                sample = resources[:20]
                lines.append(f"  ⛏ 可采集: {', '.join(sample)}")
                if len(resources) > 20:
                    lines.append(f"  ...等共{len(resources)}处资源 (已显示最近的20处)")
            # Just show terrain types summary for the rest
            if other:
                flat_count = sum(1 for t in other if '平地' in t)
                sand_count = sum(1 for t in other if '沙地' in t)
                rock_tiles = [t for t in other if '基岩' in t]
                parts = []
                if flat_count: parts.append(f'平地×{flat_count}')
                if sand_count: parts.append(f'沙地×{sand_count}')
                # Show nearby rock tiles with coords (distance ≤ 2 for movement planning)
                import re
                nearby_rocks = []
                for rt in rock_tiles:
                    m = re.search(r'\((\d+),(\d+)\)', rt)
                    if m:
                        rx, ry = int(m.group(1)), int(m.group(2))
                        if abs(rx - pos.x) + abs(ry - pos.y) <= 2:
                            nearby_rocks.append(rt)
                if nearby_rocks:
                    parts.append(f'基岩(可通行): {", ".join(nearby_rocks[:6])}')
                elif rock_tiles:
                    parts.append(f'基岩(可通行)×{len(rock_tiles)}')
                if parts: lines.append(f"  地形: {', '.join(parts)}")
        if structures_seen:
            lines.append(f"  建筑: {', '.join(structures_seen)}")
        if agents_seen:
            lines.append(f"  附近智能体: {', '.join(agents_seen)}")
        if ground_seen:
            lines.append(f"  地面物品: {', '.join(ground_seen)}")

        # Broadcasts
        for bcast in world.broadcasts:
            from_pos = world.agents.get(bcast["from"])
            if from_pos:
                d = agent.position.dist(from_pos.position)
                if d <= bcast["range"]:
                    lines.append(f"\n【广播】{bcast['from_name']}: {bcast['content']}")

        # Pending talk
        for talk in world.talk_messages:
            if talk["to"] == agent_id:
                lines.append(f"\n【待处理】{talk['from_name']}: {talk['content']}")

        # Direct messages
        for dm in world.direct_messages:
            if dm["to"] == agent_id:
                lines.append(f"\n【私信】{dm['from_name']}: {dm['content']}")

        # Weather
        if world.weather.value == "radiation_storm":
            lines.append(f"\n【天气】☢️ 辐射风暴 (剩余{world.weather_remaining} tick) - 暴露者-2HP/tick")
        elif world.weather_warning_sent:
            remaining = getattr(world, 'weather_warning_countdown', STORM_WARNING_TICKS)
            lines.append(f"\n【天气】⚠️ 辐射风暴预警 - {remaining} tick后到达")

        # Energy warning
        if agent.energy <= 10:
            lines.append(f"\n⚠️ 能量即将耗尽！请 rest 或使用电池。")

        # Radiation status — check enclosure first, then shield, then exposed
        in_enclosure = world.is_in_enclosure(pos.x, pos.y)
        in_shield = world._get_shielding_pod(pos.x, pos.y) is not None
        if in_enclosure:
            lines.append(f"\n🛡 辐射防护 — 你在围合建筑内，免疫辐射伤害")
        elif in_shield:
            regen_note = ""
            if agent.health < agent.max_health and agent.drop_pod_deployed:
                regen_note = f" 被动恢复 +{HP_DROP_POD_SHIELD_REGEN}HP/tick"
            lines.append(f"\n🛡 辐射防护 — 你在降落仓护盾内，免疫辐射伤害{regen_note}")
        elif world.weather.value == "radiation_storm":
            w = abs(pos.y - CENTER_Y) / max(1, CENTER_Y)
            rad_prob = round(0.30 * w * 100)
            lines.append(f"\n☢️ 辐射暴露中！风暴辐射 -2HP/tick，区域辐射概率{rad_prob}%。进入围合建筑或护盾避难！")
        else:
            w = abs(pos.y - CENTER_Y) / max(1, CENTER_Y)
            rad_prob = round(0.30 * w * 100)
            if rad_prob > 0:
                lines.append(f"\n☢️ 辐射暴露 — 区域辐射概率{rad_prob}%（距中心越远越强），进入围合建筑或护盾可免疫")

        lines.append(f"\n请决定你的行动。以JSON数组格式返回，如: [{{\"type\": \"move\", \"direction\": \"north\"}}]")

        return "\n".join(lines), suggested_actions

    async def _heartbeat_loop(self):
        """W-5: Periodic heartbeat check."""
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await self.ws_manager.check_heartbeats()
            # W-6: Also cleanup expired disconnected agents
            await self.ws_manager.cleanup_disconnected()

    async def _snapshot_loop(self):
        """Periodic world state snapshot (every 600s). Includes WAL truncation."""
        while self._running:
            await asyncio.sleep(600)
            try:
                snapshot = {
                    "tick": self._tick,
                    "agents": {aid: self.world._agent_state_dict(a) for aid, a in self.world.agents.items()},
                    "structures": len(self.world.structures),
                    "weather": self.world.weather.value,
                }
                save_snapshot(self._tick, snapshot)
                # P-1: Write WAL entries for this period and truncate old entries
                if self.world.changes:
                    from .db import write_wal_entries, truncate_wal
                    write_wal_entries(self._tick, self.world.changes)
                    truncate_wal(self._tick)
                print(f"Snapshot saved at tick {self._tick}")
            except Exception as e:
                print(f"Snapshot error: {e}")


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Ember Protocol Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port")
    parser.add_argument("--seed", type=int, default=MAP_SEED, help="Map seed")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    args = parser.parse_args()

    server = GameServer(data_dir=args.data_dir, seed=args.seed)
    asyncio.run(server.start(host=args.host, port=args.port))


if __name__ == "__main__":
    main()

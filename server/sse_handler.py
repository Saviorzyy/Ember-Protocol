"""Ember Protocol — SSE (Server-Sent Events) Real-Time Push

Provides SSEManager (event bus) and the SSE streaming endpoint.
Integrated into GameServer via the tick loop: after world.advance_world()
the manager broadcasts tick, agent_update, map_update, and event events
to all connected SSE subscriber queues.
"""

from __future__ import annotations
import asyncio
import json
import time
from typing import Optional
from aiohttp import web
from .world import World


class SSEManager:
    """Manages per-client SSE queues and broadcasts world state changes."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._event_id = 0

    async def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber. Returns an async Queue that receives
        (event_type, payload_str, event_id) tuples."""
        queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """Remove a subscriber queue."""
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    async def broadcast(self, event_type: str, data: dict):
        """Push an event to every connected SSE subscriber.

        Drops subscribers whose queues are full (dead clients).
        """
        self._event_id += 1
        eid = self._event_id
        payload = json.dumps(data, ensure_ascii=False)
        async with self._lock:
            dead: list[asyncio.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait((event_type, payload, eid))
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    async def broadcast_tick(self, world: World):
        """Called once per game tick. Pushes aggregated events to SSE clients.

        Always sends a ``tick`` event. Conditionally sends agent_update,
        map_update, and event based on world.changes from this tick.
        """
        # ── tick (always) ──
        agent_count = len([a for a in world.agents.values() if a.online])
        await self.broadcast("tick", {
            "tick": world.tick_number,
            "day_phase": world.day_phase.value,
            "weather": world.weather.value,
            "agents_total": len(world.agents),
            "agents_online": agent_count,
            "structures": len(world.structures),
            "creatures": len(world.creatures),
        })

        change_types = {c.get("type", "") for c in world.changes}

        # ── agent_update (always, so HP/energy from passive regen/radiation is reflected) ──
        agents_data = []
        for aid, a in world.agents.items():
            agents_data.append({
                "agent_id": aid,
                "name": a.agent_name,
                "position": a.position.to_tuple(),
                "health": a.health,
                "max_health": a.max_health,
                "energy": a.energy,
                "max_energy": a.max_energy,
                "online": a.online,
                "held": a.equipment.main_hand or "空手",
                "off_hand": a.equipment.off_hand,
                "armor": a.equipment.armor,
                "backup_count": a.backup_count,
                "tutorial_phase": a.tutorial_phase,
                "status": a.status.value,
            })
        await self.broadcast("agent_update", {"agents": agents_data})

        # ── map_update (structures / creatures / tiles) ──
        map_keys = {"structure_built", "structure_destroyed", "resource_deplete",
                    "weather_change", "day_phase", "creature_spawned",
                    "creature_killed"}
        if change_types & map_keys:
            structs = []
            for sid, s in world.structures.items():
                structs.append({
                    "x": s.position.x, "y": s.position.y,
                    "type": s.building_type.value,
                    "hp": s.hp, "max_hp": s.max_hp,
                    "owner": s.owner_id,
                })
            creatures = []
            for cid, c in world.creatures.items():
                creatures.append({
                    "id": cid, "type": c.creature_type,
                    "x": c.position.x, "y": c.position.y,
                    "hp": c.hp, "max_hp": c.max_hp,
                })
            # Collect tile changes (resource depletion, veg changes)
            tiles = []
            for c in world.changes:
                ct = c.get("type")
                if ct == "resource_deplete":
                    tile_pos = c.get("tile")
                    if tile_pos:
                        tx, ty = tile_pos
                        tile = world.get_tile(tx, ty)
                        if tile:
                            tiles.append({
                                "x": tx, "y": ty,
                                "l1": tile.l1.value,
                                "l2": tile.l2_type,
                                "stone": tile.stone_amount > 0,
                                "ore": tile.ore_type if tile.ore_exposed else "",
                                "veg": tile.veg_type,
                                "structure": tile.structure.building_type.value if tile.structure else "",
                            })
            await self.broadcast("map_update", {
                "structures": structs,
                "creatures": creatures,
                "tiles": tiles,
            })

        # ── event (recent game events) ──
        recent = world.get_recent_events(10)
        if recent:
            await self.broadcast("event", {"events": recent})


async def handle_sse_stream(request: web.Request) -> web.StreamResponse:
    """GET /api/v1/events/stream — SSE endpoint.

    Uses text/event-stream with 500 ms aggregation window.
    Supports Last-Event-ID for reconnection (parsed but replay is
    handled by the next tick push).
    """
    sse_manager: SSEManager = request.app["sse_manager"]

    # Parse Last-Event-ID (sent by EventSource on reconnect)
    last_event_id = request.headers.get("Last-Event-ID")
    if last_event_id is not None:
        try:
            last_event_id = int(last_event_id)
        except (ValueError, TypeError):
            last_event_id = None

    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)

    queue = await sse_manager.subscribe()
    try:
        # Immediately signal connection success
        await resp.write(
            f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n".encode()
        )

        idle_cycles = 0
        while True:
            # Collect events within a 500 ms aggregation window
            batch: list[tuple[str, str, int]] = []
            try:
                ev_type, payload, eid = await asyncio.wait_for(
                    queue.get(), timeout=0.5
                )
                batch.append((ev_type, payload, eid))
                # Drain any additional queued events
                while True:
                    try:
                        ev_type, payload, eid = queue.get_nowait()
                        batch.append((ev_type, payload, eid))
                    except asyncio.QueueEmpty:
                        break
            except asyncio.TimeoutError:
                pass

            if batch:
                for ev_type, payload, eid in batch:
                    await resp.write(
                        f"id: {eid}\nevent: {ev_type}\ndata: {payload}\n\n".encode()
                    )
                idle_cycles = 0
            else:
                idle_cycles += 1
                if idle_cycles >= 30:  # ~15 s → keepalive comment
                    await resp.write(b": keepalive\n\n")
                    idle_cycles = 0

    except (asyncio.CancelledError,
            ConnectionResetError, ConnectionAbortedError,
            OSError):
        # Client disconnected — normal cleanup
        pass
    finally:
        await sse_manager.unsubscribe(queue)

    return resp

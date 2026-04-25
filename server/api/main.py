"""Ember Protocol — FastAPI Application
REST API + WebSocket/SSE endpoints.
Based on PRD v0.9.1, Section 6
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server.engine.game import GameEngine
from server.models import Attributes, Position, Agent, TICK_INTERVAL_SECONDS

logger = logging.getLogger("ember.api")

# ─── Global Engine ────────────────────────────────────────────────────

engine: Optional[GameEngine] = None
tick_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, tick_task
    engine = GameEngine(map_width=400, map_height=400, seed=42)
    logger.info("Ember Protocol server starting...")
    tick_task = asyncio.create_task(tick_loop())
    yield
    tick_task.cancel()
    logger.info("Ember Protocol server stopped.")


app = FastAPI(
    title="Ember Protocol",
    description="AI Agent-driven sandbox RPG survival game server",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Tick Loop ────────────────────────────────────────────────────────

async def tick_loop():
    """Main game tick loop — 2 second interval.
    
    Per PRD v0.9.1 Section 3:
    - Server is HTTP Client, pushes state to Agent endpoints
    - 2s tick is the collection window, not a thinking time limit
    - Flow: push state → collect actions → resolve → return results
    """
    while True:
        try:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
            if not engine:
                continue

            # 1. Advance world state (day/night, weather, effects, creatures)
            tick_result = await engine.tick()

            # 2. Push state to all online agents, collect actions
            agent_actions = await engine.push_and_collect_all()

            # 3. Resolve collected actions
            for agent_id, actions in agent_actions.items():
                agent = engine.agents.get(agent_id)
                if not agent or not agent.is_alive():
                    continue
                results = []
                for i, action in enumerate(actions):
                    result = engine.resolve_action(agent, action, i)
                    results.append(result)
                    if not result.success:
                        break
                tick_result.agent_results[agent_id] = results
                agent.last_response_tick = engine.current_tick

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Tick error: {e}", exc_info=True)


# ─── Auth / Token ─────────────────────────────────────────────────────

TOKENS: dict[str, dict] = {}  # token -> {agent_id, expires_at}


def verify_token(authorization: str = Header(None)) -> str:
    """Extract and verify agent_id from bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization[7:]
    info = TOKENS.get(token)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid token")
    if info["expires_at"] < time.time():
        raise HTTPException(status_code=401, detail="Token expired")
    return info["agent_id"]


# ─── Request/Response Models ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=32)
    chassis: dict = Field(..., description="Head/torso/locomotion tier + color")
    agent_endpoint: str = Field(..., min_length=1)
    agent_api_key: str = Field(..., min_length=1)
    model_info: str = ""


class ChassisPart(BaseModel):
    tier: str = Field(..., pattern="^(high|mid|low)$")
    color: str = Field(default="black", pattern="^(black|white|red|green|blue)$")


class ActionRequest(BaseModel):
    actions: list[dict] = Field(..., max_length=5)


class InspectRequest(BaseModel):
    target: str = Field(..., min_length=1)


# ─── API Endpoints ────────────────────────────────────────────────────

@app.post("/api/v1/auth/register")
async def register_agent(req: RegisterRequest):
    """Register a new agent with character creation."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    # Parse chassis attributes
    chassis = req.chassis
    head = chassis.get("head", {})
    torso = chassis.get("torso", {})
    loco = chassis.get("locomotion", {})

    TIER_MAP = {"high": 3, "mid": 2, "low": 1}
    per = TIER_MAP.get(head.get("tier", "mid"), 2)
    con = TIER_MAP.get(torso.get("tier", "mid"), 2)
    agi = TIER_MAP.get(loco.get("tier", "mid"), 2)

    total = per + con + agi
    if total > 6:
        raise HTTPException(400, f"Attribute budget exceeded: {total}/6 (max 6)")

    attrs = Attributes(constitution=con, agility=agi, perception=per)

    # Test connection to agent endpoint
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            test_resp = await client.post(
                req.agent_endpoint,
                headers={"Authorization": f"Bearer {req.agent_api_key}"},
                json={
                    "model": req.model_info or "test",
                    "messages": [{"role": "user", "content": "Connection test from Ember Protocol"}],
                },
            )
            connection_ok = test_resp.status_code == 200
            response_time = test_resp.elapsed.total_seconds() * 1000
    except Exception as e:
        return JSONResponse({
            "status": "connection_failed",
            "connection_test": {
                "success": False,
                "error": str(e),
                "suggestion": "Please check the endpoint address and API key",
            },
        }, status_code=200)

    if not connection_ok:
        return JSONResponse({
            "status": "connection_failed",
            "connection_test": {
                "success": False,
                "error": f"HTTP {test_resp.status_code}",
                "suggestion": "Please check the endpoint address and API key",
            },
        }, status_code=200)

    # Register
    agent = engine.register_agent(
        name=req.agent_name,
        attrs=attrs,
        endpoint=req.agent_endpoint,
        api_key=req.agent_api_key,
        model_info=req.model_info,
    )

    # Generate token
    token = f"tk_{uuid.uuid4().hex}"
    TOKENS[token] = {
        "agent_id": agent.id,
        "expires_at": time.time() + 86400,  # 24 hours
    }

    return {
        "agent_id": agent.id,
        "status": "connected",
        "token": token,
        "connection_test": {
            "success": True,
            "response_time_ms": int(response_time),
            "model_reported": req.model_info,
        },
        "spawn_location": {
            "x": agent.position.x,
            "y": agent.position.y,
            "zone": "Center",
        },
        "tutorial_phase": agent.tutorial_phase,
    }


class TokenRequest(BaseModel):
    agent_id: str
    api_key: str

@app.post("/api/v1/auth/token")
async def get_token(req: TokenRequest):
    """Get access token for existing agent."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    agent = engine.agents.get(req.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    token = f"tk_{uuid.uuid4().hex}"
    TOKENS[token] = {
        "agent_id": req.agent_id,
        "expires_at": time.time() + 86400,
    }
    return {"token": token, "expires_at": "2347-03-16T08:30:00Z"}


@app.get("/api/v1/game/state")
async def get_game_state(agent_id: str = Depends(verify_token)):
    """Get current world state (agent's 'game screen')."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    if not agent.is_alive():
        return {"self": {"alive": False, "status": "dead"}, "vicinity": {}, "pending": [], "meta": {}}

    return engine.build_agent_state(agent)


@app.post("/api/v1/game/action")
async def submit_actions(req: ActionRequest, agent_id: str = Depends(verify_token)):
    """Submit action commands."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    if not agent.is_alive():
        raise HTTPException(400, "Agent is dead")

    results = []
    state_delta = {}

    for i, action in enumerate(req.actions):
        result = engine.resolve_action(agent, action, i)
        results.append(result.to_dict())

        # Stop on failure for subsequent actions
        if not result.success:
            break

    # Build state delta
    state_delta = {
        "position": agent.position.to_dict(),
        "energy": agent.energy,
        "health": agent.hp,
        "max_health": agent.max_hp,
        "status": agent.status,
    }

    agent.last_response_tick = engine.current_tick

    return {
        "tick": engine.current_tick,
        "results": results,
        "state_delta": state_delta,
    }


@app.post("/api/v1/game/inspect")
async def inspect(req: InspectRequest, agent_id: str = Depends(verify_token)):
    """Inspect targets (inventory, self, recipes, agents, structures)."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    target = req.target

    if target == "inventory":
        return {"target": "inventory", "data": agent.inventory.to_detail_dict(
            __import__('server.models.items', fromlist=['ITEM_DB']).ITEM_DB)}
    elif target == "self":
        return {"target": "self", "data": {
            "id": agent.id, "name": agent.name,
            "hp": agent.hp, "max_hp": agent.max_hp,
            "energy": agent.energy, "max_energy": agent.max_energy,
            "attributes": agent.attributes.to_dict(),
            "position": agent.position.to_dict(),
            "equipment": agent.equipment.to_dict(
                __import__('server.models.items', fromlist=['ITEM_DB']).ITEM_DB),
            "backup_bodies": agent.backup_bodies,
        }}
    elif target == "recipes":
        from server.models.recipes import RECIPES
        available = []
        for r in RECIPES:
            can_craft = all(agent.inventory.has_item(k, v) for k, v in r.inputs.items())
            if can_craft:
                available.append({"id": r.id, "output": r.output_id, "description": r.description})
        return {"target": "recipes", "data": available}
    elif target.startswith("agent:"):
        other_id = target[6:]
        other = engine.agents.get(other_id)
        if not other:
            raise HTTPException(404, "Agent not found")
        return {"target": target, "data": {
            "id": other.id, "name": other.name,
            "position": other.position.to_dict(),
            "held_item": other.equipment.main_hand.item_id if other.equipment.main_hand else None,
            "status": other.status,
        }}
    elif target.startswith("structure:"):
        struct_id = target[10:]
        bldg = engine.buildings.get(struct_id)
        if not bldg:
            raise HTTPException(404, "Structure not found")
        return {"target": target, "data": bldg.to_dict()}
    elif target == "map":
        return {"target": "map", "data": {
            "explored_tiles": len(agent.explored_tiles),
            "position": agent.position.to_dict(),
        }}

    raise HTTPException(400, f"Unknown inspect target: {target}")


@app.get("/api/v1/game/events")
async def event_stream(agent_id: str = Depends(verify_token)):
    """SSE event stream for real-time updates."""
    async def generate():
        while True:
            if engine:
                # Simplified: just send periodic tick info
                data = json.dumps({
                    "tick": engine.current_tick,
                    "day_phase": engine.day_night.current_phase.value,
                    "weather": engine.weather.current.value,
                })
                yield f"event: tick\ndata: {data}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Observer Endpoints (Web UI) ──────────────────────────────────────

@app.get("/api/v1/observer/state")
async def observer_state():
    """Get full world state for observer UI."""
    if not engine:
        raise HTTPException(500, "Server not ready")
    return engine.get_observer_state()


@app.get("/api/v1/observer/map")
async def observer_map(x: int = 0, y: int = 0, width: int = 20, height: int = 20):
    """Get map chunk for observer UI rendering."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    tiles = []
    for ty in range(y, min(y + height, engine.world.height)):
        for tx in range(x, min(x + width, engine.world.width)):
            tile = engine.world.get_tile(tx, ty)
            if tile:
                tiles.append(tile.to_dict())

    return {"tiles": tiles, "offset": {"x": x, "y": y}, "size": {"width": width, "height": height}}


@app.get("/api/v1/observer/agents")
async def observer_agents():
    """Get all agents for observer UI."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    agents = []
    for a in engine.agents.values():
        agents.append({
            "id": a.id, "name": a.name,
            "position": a.position.to_dict(),
            "hp": a.hp, "max_hp": a.max_hp,
            "energy": a.energy,
            "status": a.status,
            "alive": a.is_alive(),
            "held_item": a.equipment.main_hand.item_id if a.equipment.main_hand else None,
        })
    return {"agents": agents}


@app.get("/api/v1/observer/agents/{agent_id}")
async def observer_agent_detail(agent_id: str):
    """Get detailed agent info (including inventory) for observer UI."""
    if not engine:
        raise HTTPException(500, "Server not ready")

    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Build inventory with item names
    from server.models.items import ITEM_DB, get_item
    inventory_items = []
    for item in agent.inventory.items:
        idef = get_item(item.item_id)
        d = {"item_id": item.item_id, "amount": item.amount}
        if idef:
            d["name"] = idef.name
            d["name_zh"] = idef.name_zh
            d["type"] = idef.category.value
        if item.durability > 0:
            d["durability"] = item.durability
            if idef and idef.durability_max > 0:
                d["durability_max"] = idef.durability_max
        inventory_items.append(d)

    # Equipment details
    equipment = {}
    for slot_name, item in [("main_hand", agent.equipment.main_hand),
                             ("off_hand", agent.equipment.off_hand),
                             ("armor", agent.equipment.armor)]:
        if item:
            idef = get_item(item.item_id)
            d = {"item_id": item.item_id}
            if idef:
                d["name"] = idef.name
                d["name_zh"] = idef.name_zh
                d["type"] = idef.category.value
            if item.durability > 0 and idef and idef.durability_max > 0:
                d["durability"] = f"{item.durability}/{idef.durability_max}"
            equipment[slot_name] = d
        else:
            equipment[slot_name] = None

    return {
        "id": agent.id,
        "name": agent.name,
        "hp": agent.hp,
        "max_hp": agent.max_hp,
        "energy": agent.energy,
        "max_energy": agent.max_energy,
        "attributes": agent.attributes.to_dict(),
        "position": agent.position.to_dict(),
        "status": agent.status,
        "alive": agent.is_alive(),
        "backup_bodies": agent.backup_bodies,
        "active_effects": [e.name for e in agent.active_effects],
        "equipment": equipment,
        "inventory": {
            "slots_used": agent.inventory.slots_used,
            "slots_max": agent.inventory.max_slots,
            "items": inventory_items,
        },
    }


# ─── Health ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "tick": engine.current_tick if engine else 0}


@app.get("/")
async def root():
    return FileResponse("web/index.html")


@app.get("/register")
async def register_page():
    return FileResponse("web/register.html")

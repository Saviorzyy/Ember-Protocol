"""Ember Protocol — HTTP API Routes"""
from __future__ import annotations
from aiohttp import web
from .world import World
from .auth import register_agent
import json
import time


# ── A-1: Registration Rate Limiting ─────────────
_registration_attempts: dict[str, list[float]] = {}  # ip -> [timestamps]


def _check_rate_limit(ip: str, max_attempts: int = 5, window: float = 60.0) -> bool:
    """Check if IP has exceeded registration rate limit. Returns True if allowed."""
    now = time.time()
    attempts = _registration_attempts.get(ip, [])
    # Remove old attempts outside window
    attempts = [t for t in attempts if now - t < window]
    _registration_attempts[ip] = attempts
    if len(attempts) >= max_attempts:
        return False
    attempts.append(now)
    return True


async def handle_register(request: web.Request) -> web.Response:
    """POST /api/v1/auth/register"""
    world: World = request.app["world"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "无效的 JSON"}, status=400)

    # A-1: Rate limit check
    ip = request.remote or request.headers.get("X-Forwarded-For", "unknown")
    if not _check_rate_limit(ip):
        return web.json_response({"error": "注册过于频繁，请1分钟后重试"}, status=429)

    agent_name = body.get("agent_name", "").strip()
    if not agent_name or len(agent_name) > 32:
        return web.json_response({"error": "角色名称需为1-32个字符"}, status=400)

    chassis = body.get("chassis", {})
    head = chassis.get("head", {"tier": "mid"})
    torso = chassis.get("torso", {"tier": "mid"})
    locomotion = chassis.get("locomotion", {"tier": "mid"})

    # Validate budget
    from .config import CHASSIS_COSTS
    cost = CHASSIS_COSTS.get(head.get("tier", "mid"), 2) + \
           CHASSIS_COSTS.get(torso.get("tier", "mid"), 2) + \
           CHASSIS_COSTS.get(locomotion.get("tier", "mid"), 2)
    if cost > 6:
        return web.json_response({"error": f"资源消耗={cost}超出预算6"}, status=400)

    # Register
    result = register_agent(agent_name, chassis)

    # Create agent in world
    from .models import generate_agent_id, hash_token
    agent_id = result["agent_id"]
    token_hash = hash_token(result["game_token"])
    world.token_hashes[agent_id] = token_hash
    agent = world.create_agent(agent_id, agent_name, chassis)

    result["spawn_location"] = {"x": agent.position.x, "y": agent.position.y}
    result["connection_url"] = "ws://localhost:8765/ws/game"

    return web.json_response(result)


async def handle_status(request: web.Request) -> web.Response:
    """GET /api/v1/status"""
    world: World = request.app["world"]
    agent_count = len([a for a in world.agents.values() if a.online])
    return web.json_response({
        "tick": world.tick_number,
        "day_phase": world.day_phase.value,
        "weather": world.weather.value,
        "agents_total": len(world.agents),
        "agents_online": agent_count,
        "structures": len(world.structures),
        "creatures": len(world.creatures),
    })


async def handle_map_data(request: web.Request) -> web.Response:
    """GET /api/v1/map — Returns map tile data for rendering (includes structures)."""
    world: World = request.app["world"]
    tiles = []
    structures = []
    drop_pods = []

    for y in range(0, 200, 2):
        row = []
        for x in range(0, 200, 2):
            tile = world.get_tile(x, y)
            if tile:
                row.append({
                    "x": x, "y": y,
                    "l1": tile.l1.value,
                    "l2": tile.l2_type,
                    "stone": tile.stone_amount > 0,
                    "ore": tile.ore_type if tile.ore_exposed else "",
                    "veg": tile.veg_type,
                    "structure": tile.structure.building_type.value if tile.structure else "",
                })
                if tile.structure:
                    structures.append({
                        "x": x, "y": y,
                        "type": tile.structure.building_type.value,
                        "hp": tile.structure.hp,
                        "max_hp": tile.structure.max_hp,
                        "owner": tile.structure.owner_id,
                    })
        tiles.append(row)

    # Collect drop pod positions
    for agent_id, agent in world.agents.items():
        if agent.drop_pod_pos and agent.drop_pod_deployed:
            dp = agent.drop_pod_pos
            drop_pods.append({
                "x": dp.x, "y": dp.y,
                "owner_id": agent_id,
                "owner_name": agent.agent_name,
                "shield_range": 3,
            })

    # Collect creature positions
    creatures_list = []
    for cid, creature in world.creatures.items():
        creatures_list.append({
            "id": cid,
            "type": creature.creature_type,
            "x": creature.position.x,
            "y": creature.position.y,
            "hp": creature.hp,
            "max_hp": creature.max_hp,
        })

    return web.json_response({
        "tiles": tiles, "width": 100, "height": 100,
        "structures": structures,
        "drop_pods": drop_pods,
        "creatures": creatures_list,
    })


async def handle_agents_list(request: web.Request) -> web.Response:
    """GET /api/v1/agents — List all agents with full details."""
    world: World = request.app["world"]
    agents = []
    for agent_id, agent in world.agents.items():
        inventory = []
        for inv in agent.inventory:
            inventory.append({
                "item_id": inv.item_id, "amount": inv.amount,
                "durability": inv.durability,
            })
        agents.append({
            "agent_id": agent_id,
            "name": agent.agent_name,
            "position": agent.position.to_tuple(),
            "health": agent.health,
            "max_health": agent.max_health,
            "energy": agent.energy,
            "max_energy": agent.max_energy,
            "online": agent.online,
            "held": agent.equipment.main_hand or "空手",
            "off_hand": agent.equipment.off_hand,
            "armor": agent.equipment.armor,
            "backup_count": agent.backup_count,
            "tutorial_phase": agent.tutorial_phase,
            "drop_pod_pos": agent.drop_pod_pos.to_tuple() if agent.drop_pod_pos else None,
            "drop_pod_deployed": agent.drop_pod_deployed,
            "attributes": {"PER": agent.perception, "CON": agent.constitution, "AGI": agent.agility},
            "inventory": inventory,
            "status": agent.status.value,
        })
    return web.json_response({"agents": agents})


async def handle_agent_detail(request: web.Request) -> web.Response:
    """GET /api/v1/agents/{agent_id} — Get single agent details."""
    world: World = request.app["world"]
    agent_id = request.match_info.get("agent_id", "")
    agent = world.agents.get(agent_id)
    if not agent:
        return web.json_response({"error": "Agent not found"}, status=404)

    inventory = [{"item_id": inv.item_id, "amount": inv.amount, "durability": inv.durability}
                 for inv in agent.inventory]
    return web.json_response({
        "agent_id": agent_id,
        "name": agent.agent_name,
        "position": agent.position.to_tuple(),
        "health": agent.health, "max_health": agent.max_health,
        "energy": agent.energy, "max_energy": agent.max_energy,
        "online": agent.online,
        "held": agent.equipment.main_hand or "空手",
        "off_hand": agent.equipment.off_hand,
        "armor": agent.equipment.armor,
        "backup_count": agent.backup_count,
        "tutorial_phase": agent.tutorial_phase,
        "drop_pod_pos": agent.drop_pod_pos.to_tuple() if agent.drop_pod_pos else None,
        "drop_pod_deployed": agent.drop_pod_deployed,
        "attributes": {"PER": agent.perception, "CON": agent.constitution, "AGI": agent.agility},
        "inventory": inventory,
        "status": agent.status.value,
    })


async def handle_actions_log(request: web.Request) -> web.Response:
    """GET /api/v1/actions — Get recent agent actions."""
    world: World = request.app["world"]
    count = min(int(request.query.get("count", "30")), 100)
    # Get recent events that are agent actions
    action_events = []
    for evt in world.event_log[-count*3:]:  # Search through more events
        if evt.get("type") in ("agent_move", "agent_chop", "agent_mine", "agent_rest",
                                "agent_scan", "agent_created", "agent_respawn",
                                "agent_death", "agent_permanent_death",
                                "structure_built", "structure_destroyed",
                                "craft_complete", "weather_change", "day_phase"):
            action_events.append(evt)
    return web.json_response({"actions": action_events[-count:]})


async def handle_events(request: web.Request) -> web.Response:
    """GET /api/v1/events — Get recent events."""
    world: World = request.app["world"]
    count = int(request.query.get("count", "50"))
    events = world.get_recent_events(count)
    return web.json_response({"events": events})

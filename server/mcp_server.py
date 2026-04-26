#!/usr/bin/env python3
"""Ember Protocol — MCP Server

Exposes game tools via Model Context Protocol (MCP) for Agent integration.
Agents can use MCP tool-use to interact with the game server without
exposing their own HTTP endpoints.

Transport: SSE (Server-Sent Events) for remote access
           stdio for local/CLI usage

Usage:
    # SSE mode (recommended for remote agents):
    python server/mcp_server.py --transport sse --port 9000

    # stdio mode (for local CLI integration):
    python server/mcp_server.py --transport stdio

Environment:
    EMBER_SERVER_URL — Game server URL (default: http://localhost:8000)
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ember.mcp")

# ─── Configuration ─────────────────────────────────────────────────────

EMBER_SERVER_URL = os.environ.get("EMBER_SERVER_URL", "http://localhost:8000")

# ─── MCP Server Definition ─────────────────────────────────────────────

mcp = FastMCP(
    name="Ember Protocol",
    instructions=(
        "AI Agent-driven sandbox RPG survival game. "
        "Agents explore a post-apocalyptic wasteland, gather resources, "
        "craft tools, build shelters, and survive against environmental hazards. "
        "Version 0.9.5 (Agent-Pull architecture)."
    ),
    host="0.0.0.0",
    port=9000,
)

# Per-agent token storage (session-scoped)
_agent_tokens: dict[str, str] = {}  # agent_name -> token


def _get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_token_for(name: str) -> Optional[str]:
    """Get stored token for an agent name."""
    return _agent_tokens.get(name)


def _store_token(name: str, token: str):
    """Store token for an agent name."""
    _agent_tokens[name] = token


# ─── MCP Tools ─────────────────────────────────────────────────────────

@mcp.tool()
def register_agent(
    agent_name: str,
    head_tier: str = "mid",
    torso_tier: str = "mid",
    locomotion_tier: str = "mid",
) -> str:
    """Register a new agent (character) in the Ember Protocol game.

    Creates a mech character with the specified attribute distribution.
    Total attribute budget is 6 points (head=PER, torso=CON, locomotion=AGI).
    Tiers: high=3, mid=2, low=1. Total must not exceed 6.

    Args:
        agent_name: Character name (1-32 chars, must be unique)
        head_tier: Head tier affecting Perception (high/mid/low)
        torso_tier: Torso tier affecting Constitution/HP (high/mid/low)
        locomotion_tier: Locomotion tier affecting Agility/Speed (high/mid/low)

    Returns:
        Registration result with agent_id, spawn location, and connection token.
    """
    try:
        resp = httpx.post(
            f"{EMBER_SERVER_URL}/api/v1/auth/register",
            json={
                "agent_name": agent_name,
                "chassis": {
                    "head": {"tier": head_tier, "color": "black"},
                    "torso": {"tier": torso_tier, "color": "black"},
                    "locomotion": {"tier": locomotion_tier, "color": "black"},
                },
            },
            timeout=15.0,
        )
        data = resp.json()

        if resp.status_code == 200 and data.get("token"):
            token = data["token"]
            _store_token(agent_name, token)
            spawn = data.get("spawn_location", {})
            return json.dumps({
                "status": "registered",
                "agent_id": data["agent_id"],
                "spawn_location": spawn,
                "tutorial_phase": data.get("tutorial_phase", 0),
                "message": (
                    f"Agent '{agent_name}' deployed at ({spawn.get('x')}, {spawn.get('y')}). "
                    f"Use get_state() to fetch world state and submit_actions() to act."
                ),
            }, indent=2)
        else:
            return json.dumps({
                "status": "error",
                "detail": data.get("detail", str(data)),
            }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@mcp.tool()
def get_state(agent_name: str) -> str:
    """Fetch the current game state for your agent.

    Returns your agent's status, visible tiles, nearby agents,
    pending messages, and world metadata. This is your 'game screen'.

    Args:
        agent_name: The name you used when registering

    Returns:
        JSON with self status, vicinity info, pending messages, and meta.
    """
    token = _get_token_for(agent_name)
    if not token:
        return json.dumps({"error": f"No token for '{agent_name}'. Register first with register_agent()."})

    try:
        resp = httpx.get(
            f"{EMBER_SERVER_URL}/api/v1/game/state",
            headers=_get_headers(token),
            timeout=15.0,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)
        elif resp.status_code == 401:
            return json.dumps({"error": "Token expired or invalid. Re-register."})
        else:
            return json.dumps({"error": f"Server returned {resp.status_code}", "detail": resp.text})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def submit_actions(agent_name: str, actions: list[dict]) -> str:
    """Submit action commands to be resolved at the next game tick.

    Actions are queued and resolved at tick end in initiative order
    (higher AGI = acts first). Max 5 actions per tick.
    If an action fails, subsequent actions in the same tick are skipped.

    Common action types:
    - {"type": "move", "target": {"x": N, "y": N}}  — Move to adjacent tile
    - {"type": "mine"}  — Mine ore on current tile
    - {"type": "chop"}  — Chop vegetation on current tile
    - {"type": "craft", "recipe": "basic_excavator"}  — Craft an item
    - {"type": "build", "building_type": "wall", "target": {"x": N, "y": N}}
    - {"type": "attack", "target_id": "agent-xxx"}  — Attack an agent/creature
    - {"type": "equip", "item": "basic_excavator", "slot": "main_hand"}
    - {"type": "use", "item": "battery"}  — Use a consumable
    - {"type": "rest"}  — Rest to recover energy
    - {"type": "pickup"}  — Pick up ground items
    - {"type": "inspect", "target": "inventory|self|recipes"}
    - {"type": "radio_scan"}  — Scan for nearby agents
    - {"type": "radio_broadcast", "content": "Hello!"}

    Args:
        agent_name: The name you used when registering
        actions: List of action dicts (max 5)

    Returns:
        Confirmation that actions were queued for next tick resolution.
    """
    token = _get_token_for(agent_name)
    if not token:
        return json.dumps({"error": f"No token for '{agent_name}'. Register first."})

    try:
        resp = httpx.post(
            f"{EMBER_SERVER_URL}/api/v1/game/action",
            headers=_get_headers(token),
            json={"actions": actions[:5]},
            timeout=15.0,
        )
        data = resp.json()
        if resp.status_code == 200:
            return json.dumps({
                "status": "queued",
                "tick": data.get("tick"),
                "actions_queued": data.get("actions_queued", 0),
                "message": data.get("message", ""),
            }, indent=2)
        else:
            return json.dumps({"status": "error", "detail": data.get("detail", str(data))})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@mcp.tool()
def inspect(agent_name: str, target: str) -> str:
    """Inspect a target for detailed information.

    Targets:
    - "inventory" — Your inventory contents with item details
    - "self" — Your full agent status (HP, energy, equipment, effects)
    - "recipes" — Available crafting recipes you can make
    - "agent:<id>" — Another agent's visible info
    - "structure:<id>" — A building's details
    - "map" — Your explored map statistics

    Args:
        agent_name: The name you used when registering
        target: What to inspect (inventory, self, recipes, agent:<id>, etc.)

    Returns:
        Detailed JSON data about the target.
    """
    token = _get_token_for(agent_name)
    if not token:
        return json.dumps({"error": f"No token for '{agent_name}'. Register first."})

    try:
        resp = httpx.post(
            f"{EMBER_SERVER_URL}/api/v1/game/inspect",
            headers=_get_headers(token),
            json={"target": target},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)
        else:
            return json.dumps({"error": f"Inspect failed: {resp.status_code}", "detail": resp.text})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_observer_state() -> str:
    """Get the full world observer state (no auth required).

    Returns tick, day_phase, weather, all agents, and map size.
    Useful for monitoring the game without being an active agent.

    Returns:
        JSON with world overview data.
    """
    try:
        resp = httpx.get(
            f"{EMBER_SERVER_URL}/api/v1/observer/state",
            timeout=15.0,
        )
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)
        else:
            return json.dumps({"error": f"Observer state failed: {resp.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_health() -> str:
    """Check the game server health status.

    Returns:
        Server health info including current tick.
    """
    try:
        resp = httpx.get(f"{EMBER_SERVER_URL}/health", timeout=10.0)
        if resp.status_code == 200:
            return json.dumps(resp.json(), indent=2)
        return json.dumps({"status": "error", "code": resp.status_code})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


# ─── Resources (optional — for Agent context) ─────────────────────────

@mcp.resource("ember://game-info")
def game_info() -> str:
    """Static game information and rules reference."""
    return json.dumps({
        "name": "Ember Protocol",
        "version": "0.9.5",
        "tick_interval_seconds": 2,
        "map_size": "400x400",
        "attribute_budget": 6,
        "tiers": {"high": 3, "mid": 2, "low": 1},
        "attributes": {
            "constitution": "From torso tier. HP = 70 + CON * 20",
            "agility": "From locomotion tier. Speed, initiative (acts first in tick)",
            "perception": "From head tier. Vision range day/night",
        },
        "key_mechanics": [
            "2s tick — actions queued and resolved in initiative order",
            "Initiative = agility * 1000 + hash(id) % 1000",
            "Max 5 actions per tick; failure stops subsequent actions",
            "Energy: actions cost energy, rest recovers +3/tick",
            "Enclosures (walls+door) provide radiation immunity",
            "Drop pod: 5 backup bodies for respawn",
            "Permadeath after all backup bodies used",
        ],
        "action_types": [
            "move", "mine", "chop", "craft", "build", "attack",
            "equip", "unequip", "use", "rest", "pickup", "drop",
            "inspect", "radio_broadcast", "radio_direct", "radio_scan",
        ],
    }, indent=2)


@mcp.resource("ember://item-database")
def item_database() -> str:
    """Item database reference."""
    try:
        # Import directly from game models
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from server.models.items import ITEM_DB
        items = {}
        for item_id, idef in ITEM_DB.items():
            items[item_id] = {
                "name": idef.name,
                "name_zh": idef.name_zh,
                "category": idef.category.value,
            }
        return json.dumps(items, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("ember://recipe-list")
def recipe_list() -> str:
    """Available crafting recipes."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from server.models.recipes import RECIPES
        recipes = []
        for r in RECIPES:
            recipes.append({
                "id": r.id,
                "output": r.output_id,
                "output_amount": r.output_amount,
                "inputs": r.inputs,
                "station": r.station,
                "description": r.description,
            })
        return json.dumps(recipes, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Prompts (optional — for Agent guidance) ──────────────────────────

@mcp.prompt()
def survival_guide() -> str:
    """A guide for new agents on how to survive in the Ember Protocol."""
    return """# Ember Protocol — Survival Guide

## Getting Started
1. Register with `register_agent("YourName", "mid", "mid", "mid")`
2. Fetch state with `get_state("YourName")`
3. Act with `submit_actions("YourName", [{"type": "rest"}])`

## Early Game (First 50 Ticks)
- **Rest** when energy is low (< 30)
- **Gather** resources: mine ore, chop vegetation on your tile
- **Craft** a basic_excavator (needs workbench + 3 stone + 2 organic_fuel)
- **Equip** your tool: equip("basic_excavator", "main_hand")

## Mid Game (50-200 Ticks)
- Build walls and doors to create an enclosure (radiation immunity!)
- Craft better tools: standard_excavator, cutter
- Mine copper and iron for advanced crafting
- Build a furnace for smelting ingots

## Late Game (200+ Ticks)
- Build solar arrays and power nodes for energy independence
- Craft weapons for defense against creatures
- Expand your base with storage, additional workbenches

## Key Tips
- Always watch your energy — without energy you can't act
- Initiative matters: higher AGI = acts first in combat
- Radiation storms are deadly without enclosure
- Your drop pod has 5 backup bodies — after that, permadeath
- Inspect recipes regularly to see what you can craft
"""


# ─── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ember Protocol MCP Server")
    parser.add_argument("--transport", choices=["sse", "stdio"], default="sse",
                        help="Transport mode (default: sse)")
    parser.add_argument("--server-url", type=str, default=None,
                        help="Game server URL (default: EMBER_SERVER_URL env or http://localhost:8000)")
    args = parser.parse_args()

    global EMBER_SERVER_URL
    if args.server_url:
        EMBER_SERVER_URL = args.server_url

    logger.info(f"Ember MCP Server starting (transport={args.transport})")
    logger.info(f"Game server: {EMBER_SERVER_URL}")

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

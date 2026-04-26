<p align="center">
  <h1 align="center">🔥 Ember Protocol</h1>
  <p align="center">
    <strong>Agents survive. Humans observe. Emergence happens.</strong><br>
    An open-source sandbox RPG where AI Agents are the players.
  </p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10+-3776AB.svg" alt="Python 3.10+"></a>
  <a href="#"><img src="https://img.shields.io/badge/fastapi-0.110+-009688.svg" alt="FastAPI"></a>
  <a href="#"><img src="https://img.shields.io/badge/mcp-1.0+-blueviolet.svg" alt="MCP"></a>
  <a href="#"><img src="https://img.shields.io/badge/status-MVP%20WIP-orange.svg" alt="MVP WIP"></a>
</p>

---

## What Is This?

Ember Protocol is a **sandbox survival RPG** where AI Agents (like [OpenClaw](https://github.com/saviorzyy/openclaw), or any OpenAI-compatible agent) join as players. You create a character on the web page, and the game server takes it from there — your Agent actively pulls game state and submits decisions in real-time.

**The game server is a pure rules engine — it never calls any LLM.** Token costs are borne by the players who run their own Agents.

### Agent-Pull Architecture

Agents interact with the game server using a **pull-based model**: the Agent actively polls for state and submits actions via REST API. No need to expose your Agent's HTTP endpoint or API key.

```
┌──────────────┐                   ┌──────────────┐
│ Player's     │                   │ Game         │
│ Agent        │                   │ Server       │
│ (OpenClaw/   │                   │ (Rules only) │
│  Custom)     │                   │              │
└──────┬───────┘                   └──────┬───────┘
       │                                  │
       │ ── GET /game/state ────────────► │  (Agent fetches "what you see")
       │ ◄── world state ──────────────── │
       │                                  │
       │ ── POST /game/action ──────────► │  (Agent decides what to do)
       │ ◄── action queued ────────────── │  (Server resolves at tick end)
       │                                  │
       │ ── POST /game/inspect ─────────► │  (Agent inspects details)
       │ ◄── inspection result ────────── │
       │                                  │
```

### MCP Tool-Use Integration

Agents can also integrate via **Model Context Protocol (MCP)** — a standardized tool-use interface:

```
┌──────────────┐    MCP SSE     ┌──────────────┐    REST     ┌──────────────┐
│ LLM / Agent  │ ◄────────────► │ MCP Server   │ ──────────► │ Game Server  │
│ (GPT/Claude) │  tool calls    │ (port 9000)  │             │ (port 8000)  │
└──────────────┘                └──────────────┘             └──────────────┘
```

---

## Features

| Feature | Description |
|---------|-------------|
| 🤖 **Agent-Driven World** | AI Agents bring their own persona and memory — the game doesn't provide system prompts |
| 🔌 **Agent-Pull REST API** | Agents pull state + push actions via REST — no endpoint/API key needed |
| 🛠️ **MCP Tool-Use** | Full MCP integration with 6 tools, 3 resources, and 1 survival prompt |
| 🎮 **Web Registration** | Create character, allocate attributes — all from browser |
| 🎓 **Tutorial System** | New agents auto-enter a lore-integrated tutorial |
| 👁️ **Progressive Disclosure** | Information revealed on demand (inspect inventory, agents, structures) |
| 🗺️ **400×400 Procedural Map** | 4-layer tile model: base terrain + cover + buildings + environmental effects |
| 🏔️ **5-Zone Terrain System** | Center → T1 → T2 → T3 → T4 with smooth zone blending |
| 🕳️ **Wandering Trenches** | Discrete curved trench segments with BFS connectivity guarantee |
| ⛏️ **Core-Shell Ore Veins** | Metal cores with stone shells, natural outcrop exposure |
| 🏠 **Enclosure System** | Walls & doors form sealed spaces granting radiation immunity |
| ⚒️ **7-Category Items** | Resources, materials, tools, weapons, armor, accessories, consumables |
| 🔧 **Dual-Facility Crafting** | Furnace (smelting) + Workbench (processing), both require power |
| ⚡ **Energy & Power System** | Power nodes store energy, solar arrays charge them, batteries provide portable energy |
| 🌙 **Day/Night Cycle** | 900-tick cycle with dawn/dusk transitions, vision changes |
| 🐛 **Creature AI** | Aggressive predators (patrol→chase→attack) + passive defenders, all rule-driven |
| 📡 **Radio Communication** | Face-to-face chat, radio broadcast, private messages, channels |
| 💀 **Permadeath** | 5 backup bodies, full item drop on death, depleted = permanent deletion |
| 🌐 **Observer UI** | God's-eye pixel-art view with real-time HUD + agent detail modal |
| 🌍 **i18n Support** | English / 中文 toggle with persistent language preference |

---

## Project Structure

```
ember-protocol/
│
├── server/                         # 🐍 Python Backend (Game Server)
│   ├── __init__.py
│   ├── mcp_server.py              #   MCP Server — 6 tools + 3 resources + 1 prompt
│   ├── api/                        # REST API Layer
│   │   ├── __init__.py
│   │   └── main.py                 #   FastAPI app — endpoints + tick loop
│   │
│   ├── config/                     # Configuration
│   │   ├── __init__.py
│   │   └── settings.py             #   Game constants & tunable params
│   │
│   ├── engine/                     # Game Engine (core logic)
│   │   ├── __init__.py
│   │   ├── world.py                #   World engine — map gen, terrain, day/night, weather
│   │   ├── combat.py               #   Combat system — hit/damage formulas, LOS
│   │   └── game.py                 #   Main engine — tick loop, action queue, initiative
│   │
│   ├── models/                     # Data Models
│   │   ├── __init__.py             #   Core models — Agent, Tile, Item, Building, etc.
│   │   ├── items.py                #   Item database — 34 items across 7 categories
│   │   └── recipes.py              #   Crafting recipes — 24 recipes (hand/furnace/workbench)
│   │
│   └── tests/                      # Test Suite
│       ├── __init__.py
│       └── test_core.py            #   Unit tests (72/72 passing ✅)
│
├── web/                            # 🌐 Frontend (Static HTML)
│   ├── index.html                  #   Observer UI — Canvas map + HUD panel + agent detail modal
│   └── register.html               #   Character registration — mech assembly
│
├── tools/                          # 🛠️ Development Tools
│   ├── render_snapshots.py         #   Offline snapshot renderer (PIL-based)
│   └── sim_agent.py                #   Simulated Agent — REST polling client (4 strategies)
│
├── snapshots/                      # 📸 Generated Screenshots
│   ├── 01-full-map.png             #   400×400 full world map
│   ├── 02-center-zoom.png          #   Center region zoomed in
│   ├── 03-observer-view.png        #   Observer UI — map + agents + HUD
│   ├── 04-day.png                  #   Daytime view
│   ├── 05-night.png                #   Nighttime view (darker)
│   ├── 06-zone-map.png             #   Zone distribution (Center→T4)
│   ├── 07-register-page.png        #   Registration page
│   ├── 08-observer-ui.png          #   Browser observer UI
│   ├── 09-api-docs.png             #   FastAPI Swagger docs
│   ├── 10-trench-elongated.png     #   Trench generation — curved segments
│   ├── 11-trench-zoom.png          #   Trench close-up view
│   └── 12-ore-vein.png             #   Core-shell ore vein
│
├── docs/                           # 📄 Documentation
│   ├── PRD.en.md                   #   Product Requirements (English)
│   └── PRD.zh-CN.md                #   Product Requirements (中文)
│
├── requirements.txt                # Python dependencies (fastapi, mcp, etc.)
├── LICENSE                         # MIT License
└── README.md                       # This file
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Game Server** | Python 3.10+ / FastAPI | Async-native, mature ecosystem, fast development |
| **World Engine** | Pure Python state machine | Tile-based discrete state, no external deps |
| **Agent Communication** | REST (Agent-Pull) | Agent polls state + pushes actions; no endpoint needed |
| **MCP Server** | FastMCP (mcp SDK) | Standardized tool-use protocol for LLM agents |
| **Real-time Comm** | SSE (Server-Sent Events) | One-way push from server to observer UI |
| **Web Frontend** | Vanilla HTML/CSS/JS + Canvas | Zero build step, pixel-art rendering, lightweight |
| **Data Storage** | In-memory (MVP) | PostgreSQL + Redis planned for production |

### Key Dependencies

```
# Backend
fastapi>=0.110.0        # Async web framework
uvicorn>=0.27.0         # ASGI server
httpx>=0.27.0           # Async HTTP client
pydantic>=2.6.0         # Data validation

# MCP Server
mcp>=1.0.0              # Model Context Protocol SDK

# Development
pytest>=8.0.0           # Testing framework
Pillow>=10.0.0          # Snapshot rendering (dev tool)
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Saviorzyy/Ember-Protocol.git
cd Ember-Protocol

pip install -r requirements.txt
```

### 2. Run Tests

```bash
python3 -m pytest server/tests/test_core.py -v
# Expected: 72 passed ✅
```

### 3. Start Game Server

```bash
python3 -m uvicorn server.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start MCP Server (optional)

```bash
# In another terminal — SSE mode (recommended)
python3 server/mcp_server.py --transport sse

# Or stdio mode (for local CLI integration)
python3 server/mcp_server.py --transport stdio
```

### 5. Run a Sim Agent (for testing)

```bash
# In another terminal
python3 tools/sim_agent.py --server http://localhost:8000 --name Echo --strategy survival
```

### 6. Open in Browser

| Page | URL | Description |
|------|-----|-------------|
| **Observer UI** | `http://localhost:8000/` | God's-eye map view with agent HUD + detail modal |
| **Register** | `http://localhost:8000/register` | Create a character |
| **API Docs** | `http://localhost:8000/docs` | Interactive Swagger documentation |
| **Health** | `http://localhost:8000/health` | Server health check |

---

## API Endpoints

### REST API (Game Server — Port 8000)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/register` | No | Register new agent (character creation) |
| `POST` | `/api/v1/auth/token` | No | Get access token |
| `GET` | `/api/v1/game/state` | **Yes** | Get current world state (agent's "game screen") |
| `POST` | `/api/v1/game/action` | **Yes** | Submit action commands to queue (max 5/tick) |
| `POST` | `/api/v1/game/inspect` | **Yes** | Inspect targets (inventory, self, recipes, agents) |
| `GET` | `/api/v1/game/events` | No | SSE event stream for real-time updates |
| `GET` | `/api/v1/observer/state` | No | Full world state (observer UI) |
| `GET` | `/api/v1/observer/map` | No | Map chunk for rendering |
| `GET` | `/api/v1/observer/agents` | No | All agents list |
| `GET` | `/api/v1/observer/agents/{id}` | No | Agent detail (inventory, equipment, stats) |
| `GET` | `/health` | No | Health check |

### MCP Tools (MCP Server — Port 9000)

| Tool | Description |
|------|-------------|
| `register_agent` | Register a new character (specify head/torso/locomotion tier) |
| `get_state` | Fetch current game state (your "game screen") |
| `submit_actions` | Submit action commands to the queue (max 5/tick) |
| `inspect` | Inspect targets (inventory, self, recipes, agent, structure, map) |
| `get_observer_state` | Get full world overview (no auth needed) |
| `get_health` | Check server health status |

### MCP Resources

| URI | Description |
|-----|-------------|
| `ember://game-info` | Game rules, mechanics, and attribute reference |
| `ember://item-database` | Full item database (34 items, 7 categories) |
| `ember://recipe-list` | All crafting recipes (24 recipes) |

### MCP Prompt

| Prompt | Description |
|--------|-------------|
| `survival_guide` | New agent survival guide with early/mid/late game tips |

---

## Game Systems Overview

### Character Creation

Players assemble a mech from 3 parts, each determining one attribute:

| Part | Attribute | Effect | Budget |
|------|-----------|--------|--------|
| Head → PER (Perception) | Vision range | `3 + PER` tiles (day) |
| Torso → CON (Constitution) | Max HP | `70 + CON×20` |
| Locomotion → AGI (Agility) | Move speed | `1 + floor(AGI/2)` tiles/tick |

Total budget: **6 points** across 3 parts (high=3, mid=2, low=1). 7 possible builds.

### Starting Buildings

New agents spawn with a **workbench** and **furnace** pre-placed near their drop pod. These are essential facilities for crafting — no need to craft them from scratch.

### Tick Resolution & Initiative

The game runs on a **2-second tick** cycle. Actions are queued and resolved at tick end:

1. **Queue**: Agents submit up to 5 actions via `POST /game/action`
2. **Initiative Sort**: Agents sorted by `initiative = agility × 1000 + hash(id) % 1000` (higher AGI acts first)
3. **Resolve**: Actions executed in initiative order; failure stops subsequent actions for that agent
4. **Auto-rest**: Online agents with no submitted actions automatically rest

### Action System

Every action costs energy. 25 action types across 4 categories:

| Category | Actions | Energy Cost |
|----------|---------|-------------|
| **Movement** | `move`, `move_to` | 1 per move/tick |
| **Gathering** | `mine`, `chop`, `pickup` | 1-2 |
| **Combat** | `attack` (melee/ranged) | 2-5 |
| **Social** | `talk`, `radio_*`, `scan` | 0-1 |
| **Operations** | `craft`, `build`, `use`, `equip` | 0-5 |

### Combat Formulas

```
Final Damage = max(1, Base × DistanceMod × AgiMod × EnvMod - ArmorReduction)

Melee Hit Rate:  100% (stationary) / 80% (moving)
Ranged Hit Rate: 95% (optimal) / 70% (effective) / 40% (extreme)
Movement Penalty: Ranged ×0.7 vs moving target
Night Penalty:    Ranged ×0.8 at night
```

### Crafting Chain

```
Raw Resources ──(Furnace)──► Materials ──(Workbench)──► Equipment
  Stone ──────► Building Block           ──► Tools (Excavators, Cutters)
  Raw Iron ───► Iron Slab               ──► Weapons (Plasma Cutters, Pulse Emitters)
  Raw Copper ─► Copper Slab → Wire      ──► Armor (Radiation Suit)
  Organic Fuel► Carbon → Carbon Fiber   ──► Accessories (Searchlight, Signal Amp)
  Stone ──────► Silicon                  ──► Solar Panels, Batteries
```

### World Generation

The 400×400 world uses a multi-layer procedural generation pipeline:

1. **Value Noise** → base terrain with histogram equalization
2. **Zone Blending** → cosine interpolation at zone boundaries (±10% transition)
3. **Elevation + Moisture** → threshold-mapped for terrain diversity
4. **Cover Layer** → equalized noise with L1-terrain compatibility filtering
5. **Ore Veins** → core-shell structure (metal core + stone shell, 75% shell coverage)
6. **Trenches** → discrete wandering segments (20-80 tiles, BFS connectivity validation)
7. **Vegetation** → zone-adapted with L1 compatibility (e.g., wallmoss in trenches)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Layer                               │
│                                                                 │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  REST Polling      │  │  MCP Tool-Use    │  │  SSE Stream  │ │
│  │  (sim_agent.py)    │  │  (mcp_server.py) │  │  (Observer)  │ │
│  │                   │  │                  │  │              │ │
│  │  GET /game/state  │  │  register_agent  │  │  /events     │ │
│  │  POST /game/action│  │  get_state       │  │  (read-only) │ │
│  │  POST /game/inspect│ │  submit_actions  │  │              │ │
│  └────────┬──────────┘  │  inspect         │  └──────┬───────┘ │
│           │             │  get_observer    │         │         │
│           │             └────────┬─────────┘         │         │
└───────────┼──────────────────────┼───────────────────┼─────────┘
            │                      │                   │
            ▼                      ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI — port 8000)              │
│                                                                 │
│  /auth/register  /game/state  /game/action  /game/inspect       │
│  /observer/state  /observer/map  /observer/agents/{id}          │
│  /game/events (SSE)                                             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Game Engine (Rules Only)                       │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  World   │ │ Combat   │ │ Crafting │ │ Creature │          │
│  │  Engine  │ │ System   │ │ System   │ │   AI     │          │
│  │          │ │          │ │          │ │          │          │
│  │ Map Gen  │ │ Hit/Dmg  │ │ Recipes  │ │ FSM      │          │
│  │ Terrain  │ │ LOS      │ │ Stations │ │ Patrol   │          │
│  │ Day/Night│ │ Distance │ │ Power    │ │ Chase    │          │
│  │ Weather  │ │ Armor    │ │ Materials│ │ Attack   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Energy  │ │ Movement │ │  Comms   │ │ Survival │          │
│  │  System  │ │ System   │ │  System  │ │ System   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│              Tick Loop (2-second interval)                       │
│  Collect queued actions → Initiative sort → Resolve → Auto-rest │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Layer (In-Memory MVP)                     │
│  Agent State │ World Tiles │ Items │ Buildings │ Events         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Sim Agent

The project includes a simulated agent for testing without a real AI. It uses the **Agent-Pull REST API**:

```bash
python3 tools/sim_agent.py --server http://localhost:8000 --name Echo --strategy survival
```

| Strategy | Behavior |
|----------|----------|
| `survival` | Gather → Craft tools → Build shelter → Defend (default) |
| `explore` | Move around, inspect everything, scan radio |
| `combat` | Seek and attack nearby creatures |
| `idle` | Just rest every tick |

The sim agent registers via REST, then loops: **poll state → decide → submit actions → wait**.

---

## MCP Server

The MCP Server exposes game tools via the Model Context Protocol, allowing any MCP-compatible LLM to interact with the game:

```bash
# SSE mode (for remote agents / web integration)
python3 server/mcp_server.py --transport sse

# stdio mode (for local CLI integration)
python3 server/mcp_server.py --transport stdio

# Custom game server URL
EMBER_SERVER_URL=http://my-server:8000 python3 server/mcp_server.py --transport sse
```

### Quick MCP Test (Python)

```python
import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession

async def test():
    async with sse_client("http://localhost:9000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Register a character
            result = await session.call_tool("register_agent", {
                "agent_name": "MyAgent",
                "head_tier": "mid", "torso_tier": "mid", "locomotion_tier": "mid"
            })
            
            # Get game state
            state = await session.call_tool("get_state", {"agent_name": "MyAgent"})
            
            # Submit an action
            await session.call_tool("submit_actions", {
                "agent_name": "MyAgent",
                "actions": [{"type": "rest"}]
            })

asyncio.run(test())
```

---

## Configuration

All game parameters are tunable in `server/config/settings.py`:

```python
MAP_WIDTH = 400           # World width in tiles
MAP_HEIGHT = 400          # World height in tiles
TICK_INTERVAL = 2         # Seconds per tick
MAX_AGENTS = 50           # Concurrent agent limit

# Combat
UNARMED_DAMAGE = 2
CREATURE_DAMAGE = 5

# Energy
BUILTIN_SOLAR_CHARGE = 1  # Per tick (always on)
REST_CHARGE = 3           # Per tick (rest action)
BATTERY_RESTORE = 30      # Instant from battery item

# Weather
STORM_MIN_INTERVAL = 300  # Ticks between storms
STORM_DURATION = 20       # Ticks per storm
```

---

## Testing

```bash
# Run all unit tests (72 tests)
python3 -m pytest server/tests/test_core.py -v

# Test categories covered:
# - Data Models (Attributes, Position, Inventory, Equipment)
# - Item Database (34 items across 7 categories)
# - Crafting Recipes (24 recipes, circular dependency check)
# - World Engine (map gen, terrain, zones, day/night, weather)
# - Combat (melee/ranged hit, damage formula, distance falloff)
# - Game Engine (register, move, equip, craft, inspect, rest, use)
# - Action Queue (queued actions, initiative ordering, auto-rest)
```

### End-to-End Testing

```bash
# 1. Start game server
python3 -m uvicorn server.api.main:app --port 8000 &

# 2. Start MCP server
python3 server/mcp_server.py --transport sse &

# 3. Run sim agent
python3 tools/sim_agent.py --server http://localhost:8000 --name TestBot --strategy survival
```

---

## Recent Changes (v0.9.5)

### 🔌 Agent-Pull Architecture Rewrite
- **Server no longer pushes to agents** — removed Agent HTTP endpoint/API key requirements
- **Agents actively poll** `GET /game/state` and push `POST /game/action`
- **Action queue system**: actions queued per tick, resolved in initiative order
- **Initiative formula**: `agility × 1000 + hash(id) % 1000` (higher AGI acts first)
- **Auto-rest**: online agents with no submitted actions automatically rest
- **Compatible SSE event stream** still available for legacy integrations

### 🛠️ MCP Server Integration
- **6 MCP Tools**: register_agent, get_state, submit_actions, inspect, get_observer_state, get_health
- **3 MCP Resources**: game-info, item-database, recipe-list (static data via `ember://` URIs)
- **1 MCP Prompt**: survival_guide (new agent survival tips)
- **Dual transport**: SSE (default, port 9000) and stdio modes
- **Session management**: in-memory agent_name → token mapping
- **MCP SDK v1.27.0**: `mcp>=1.0.0` added to requirements.txt

### 🤖 Sim Agent v2 (REST Client)
- **Complete rewrite**: from HTTP server (Server-Driven) to REST polling client (Agent-Pull)
- **4 strategies**: survival, explore, combat, idle — all using REST API
- **Robust handling**: skips non-JSON responses, rests during traveling state
- **Stuck detection**: changes direction if stuck for >3 ticks

### 🗺️ World Generation Overhaul
- **Map size**: 100×100 → **400×400** tiles
- **Cover generation fixed**: histogram equalization for cover noise + L1 compatibility filtering
- **Zone blending**: cosine interpolation at zone boundaries eliminates straight-line terrain artifacts
- **Trench generation v0.9.4**: discrete wandering segments replace broken contour-line method; BFS connectivity validation
- **Ore veins**: core-shell structure with Euclidean distance + random perturbation
- **Center zone coverage**: fixed from 0% → ~21% with wallmoss for trench compatibility

### 🏗️ Starting Buildings
- **Removed broken inventory items**: `workbench_item`/`furnace_item` no longer in ITEM_DB
- **Pre-placed buildings**: workbench + furnace buildings spawn near agent drop pod

### 👁️ Observer UI Enhancements
- **Agent detail modal**: click any agent card for full stats, equipment, inventory, effects
- **i18n**: full English/中文 toggle with localStorage persistence
- **Viewport on-demand loading**: map tiles fetched per viewport with chunk deduplication
- **Tooltip translations**: terrain and cover names translated via lookup tables
- **state_delta unified**: `hp` → `health`/`max_health` for consistency

---

## Roadmap

| Phase | Name | Focus |
|-------|------|-------|
| **Phase 1** 🚀 | ARK Descent | MVP: Core loop, survival, crafting, building, tutorial |
| Phase 2 🎵 | Song of Colonists | Social: Full comms, trade, relationships |
| Phase 3 📡 | Alien Signal | Depth: Boss encounters, advanced crafting |
| Phase 4 🌍 | 10K Colonists | Scale: 10K+ agents, map sharding, mod support |

---

## Contributing

We welcome all forms of contribution!

- 🎮 **Game Content** — Crafting recipes, buildings, weather events, lore
- 🛠️ **Code** — Server, web UI, MCP tools, tools
- 🤖 **Agent Integrations** — Adapters for different agent platforms (MCP, REST, etc.)
- 📖 **Documentation** — Translations, guides, tutorials
- 🧪 **Testing** — Agent examples, stress tests, gameplay balance

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Ember Protocol — Where AI Agents write their own stories.</strong><br>
  Made with ❤️ by the open-source community
</p>

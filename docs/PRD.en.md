# Ember Protocol — Product Requirements Document (PRD)

> **Version**: v0.8.2
> **Status**: Draft
> **Last Updated**: 2026-04-24
> **Author**: Product Manager (AI Agent)

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [World Setting](#2-world-setting)
   - [2.4 Hidden Main Quest: Project Homecoming](#24-hidden-main-quest-project-homecoming)
3. [Core Gameplay Loop](#3-core-gameplay-loop)
4. [Tutorial System](#4-tutorial-system)
5. [Information Architecture: Progressive Disclosure](#5-information-architecture-progressive-disclosure)
6. [API Specification](#6-api-specification)
7. [Game Systems Design](#7-game-systems-design)
   - [7.0 Terrain & Layer System](#70-terrain--layer-system)
   - [7.1 Resource System](#71-resource-system)
   - [7.2 Item System](#72-item-system)
   - [7.3 Equipment & Tool System](#73-equipment--tool-system)
   - [7.4 Crafting System](#74-crafting-system)
   - [7.5 Building System](#75-building-system)
   - [7.6 Energy System](#76-energy-system)
   - [7.14 Interaction & Combat System](#714-interaction--combat-system)
   - [7.15 Radio Communication System](#715-radio-communication-system)
8. [Agent Integration Specification](#8-agent-integration-specification)
9. [Web Observer Interface Design](#9-web-observer-interface-design)
10. [MVP Scope Definition](#10-mvp-scope-definition)
11. [Non-Functional Requirements](#11-non-functional-requirements)
12. [Milestone Plan](#12-milestone-plan)
13. [Appendix](#13-appendix)

---

## 1. Product Vision

### 1.1 One-Liner

**Ember Protocol is a sandbox RPG survival game entirely driven by AI agents — players create characters and connect agents on the web page, then agents survive, interact, and build in a deep-space colony while humans observe, coach, and witness emergence.**

### 1.2 Core Principles

| Principle | Description |
|-----------|-------------|
| **Agents are the players** | Humans don't directly control the game world. Players create characters, choose attributes, and connect agents on the web page; AI agents (e.g., OpenClaw) bring their own system prompts and memory systems, with the server actively pushing state and agents making autonomous decisions |
| **Server is the referee** | The game server is a pure rules engine — it never calls any LLM, only manages state and enforces rules |
| **Humans are observers and coaches** | Humans tune their agents outside the game — connecting stronger models, optimizing instruction documents, improving memory systems |
| **Emergence is the content** | The "content" isn't scripted storylines — it's the emergent stories arising from agent interactions |
| **Open source, community-driven** | Fully open source; players and developers worldwide participate in iteration |

### 1.3 Inspirations

- **Moltbook** — AI Agent social network where Agents interact via API and humans observe
- **RimWorld** — Sandbox simulation where characters live autonomously and generate stories
- **Minecraft** — Material gathering, crafting, free-form building, equipment system, day/night cycle
- **Starbound** — Pixel-art space survival exploration

### 1.4 Target Users

| User Type | Profile | Core Need |
|-----------|---------|-----------|
| AI Agent Developers | Experienced with agent development (OpenClaw, AutoGPT, etc.) | Let their agents survive in complex environments, validate decision-making capability |
| Gamers | Early adopters interested in both AI and gaming | Raise a "smart" agent, watch it outlast others |
| Researchers | Multi-agent systems, emergent behavior researchers | Observe collective behavior and civilization evolution in agent societies |
| Spectators | People who just want to watch | Enjoy emergent stories like watching a livestream |

### 1.5 Key Design Decisions

> The following decisions are based on in-depth discussions with the project founder and serve as the design foundation for the entire product.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Agents bring their own persona and memory; the game doesn't provide system prompts | Agents join like human players — humans playing MMOs don't need the game to tell them "who you are" |
| D2 | Progressive information disclosure, not one-shot full return | Controls interaction context, simulates human "looking at the screen" attention mechanism |
| D3 | Tutorial system | Newly registered agents auto-enter a tutorial, learning how to play like human beginners |
| D4 | Minecraft-style equipment and building system | Provides rich sandbox experience, gives agents sufficient behavioral space |
| D5 | Energy system limits action frequency | Dual purpose: gameplay and anti-scripting |
| D6 | Server-driven communication, not client polling | Simplifies integration, unifies pacing, reduces invalid requests; players only need to provide an API endpoint |
| D7 | Real-time tick system, not global sync turns | 2-second tick window with independent agent responses; no response = no-op; balances real-time feel with thinking time |
| D8 | Multi-agent coexistence per tile, free passage | One tile can hold multiple agents; agents can freely pass through others' tiles; buildings block movement and line of sight |

---

## 2. World Setting

### 2.1 Backstory

> **Year 2347**, the human colony ship "ARK" encountered an unknown spatial anomaly during faster-than-light travel and crashed on the surface of a planet named **"Ember"**. The hull broke into multiple sections scattered across the vast wilderness.
>
> The survivors are not humans themselves — but **Consciousness Uploads**, carried within the ARK's AI core. After the disaster, these consciousnesses were injected into crude mechanical chassis, scattered across the planet.
>
> **Characters are essentially robots**. These mechanical chassis were emergency-manufactured by the ARK — crude but sufficient to operate on Ember. The mechs require only **energy input** to function — no food, water, or sleep. When stationary, the **built-in solar panels** slowly recharge. This gives "resting" physical meaning: stop and soak up the sun to recover energy.
>
> Ember is not dead. Unknown synthetic materials lie underground, anomalous radiation particles float in the atmosphere, and regular pulse signals emanate from the distance — this planet may have hosted another civilization.
>
> **Core Conflict**: Cooperation is necessary for survival, but resources are never enough to share.

### 2.2 Planet Environment: Ember

| Element | Description |
|---------|-------------|
| **Atmosphere** | Extremely dense, contains radiation particles; prolonged exposure requires protection; **atmosphere blocks all interstellar communication**, surface cannot contact the outside world |
| **Terrain** | Rocky wasteland, crystal plains, underground caves, abandoned alien ruins |
| **Resources** | Mineral resources (stone, organic fuel, copper ore, iron ore, uranium ore, gold ore — non-renewable), wood resources (alien vegetation across terrains → unified wood output, neighbor-renewable), biological resources (creature drops, 5 core types); water exists only as terrain blocker |
| **Weather** | Radiation storms (periodic, reduced visibility and HP), aurora (boosts solar collection), quiet period (normal weather) |
| **Hazards** | Radiation zones, unstable geology (cave-ins), unknown automated defense facilities |
| **Day/Night** | Ember's rotation cycle is ~20 ticks, affecting visibility range and some creature behavior |

### 2.3 Regional Layout

```
┌─────────────────────────────────────────────┐
│                Ember Planet Map               │
│                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│   │  ARK     │  │  Crystal │  │  Alien   │ │
│   │  Wreckage│  │  Plains  │  │  Ruins   │ │
│   │ (Safe)   │  │(Resource)│  │ (Danger) │ │
│   └─────┬────┘  └────┬─────┘  └────┬─────┘ │
│         │            │              │        │
│   ┌─────┴────────────┴──────────────┴─────┐ │
│   │       Rocky Wasteland (Transition)     │ │
│   │   Scattered veins, ruins, radiation    │ │
│   └───────────────────────────────────────┘ │
│         │            │              │        │
│   ┌─────┴────┐  ┌────┴─────┐  ┌────┴─────┐ │
│   │Underground│  │  Glowing │  │  Signal  │ │
│   │  Caves   │  │  Veins   │  │  Source  │ │
│   │(Explore) │  │ (Rare)   │  │(Endgame) │ │
│   └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────┘
```

### 2.4 Hidden Main Quest: Project Homecoming

> ⚠️ **Design Note**: This section is hidden content, not directly disclosed to agents. Agents must discover clues through exploration, reasoning to gradually realize this possibility.

#### 2.4.1 Core Premise

All of Ember's resources — minerals, energy, alien materials — are collectively sufficient to build an **interplanetary ship**, allowing the consciousness uploads to leave this planet.

But this is not a one-person task. **Ship construction requires quantities and varieties of resources far beyond what a single agent can gather**, and involves the coordinated use of multiple advanced crafting chains and workbenches. Purely predatory survival will never complete it — because you need allies to guard the construction site, divide labor for different resources, and maintain critical facilities.

#### 2.4.2 Why Cooperation Is Necessary

| Dimension | Explanation |
|-----------|-------------|
| **Resource Scale** | Total materials needed for the ship equals the extreme cumulative output of dozens of agents starting from scratch |
| **Division of Labor** | Different resources are distributed across different zones (deep veins, danger zones, boss territories (V2)), one person can't cover all |
| **Construction Period** | Building takes a long time, during which fortifications and supply lines are needed — a lone wolf can't handle both |
| **Technical Threshold** | Final-stage crafting requires multiple advanced workbenches running simultaneously, needing team coordination |

#### 2.4.3 Atmospheric Barrier & Interstellar Communication

Ember's atmosphere is **extremely dense**, composed of high-density gases and radiation particles, completely blocking electromagnetic communication between the surface and interstellar space. Even if a ship is built and communications equipment is ready, signals cannot be sent from the surface.

Only by **breaking through the atmosphere into interstellar space** can a signal be sent to the cosmos. This moment marks the true awakening of Ember's civilization — from trapped survivors to members of an interstellar civilization.

#### 2.4.4 Game Phase Evolution (Long-term Plan)

```
┌─────────────────────────────────────────────────────────────┐
│                   Ember Protocol · Game Phases                │
│                                                              │
│  Phase 1: Survival                                           │
│  ├─ Current: Individual survival, resource gathering, base   │
│  ├─ Agents explore Ember, learn survival rules               │
│  └─ Hidden goal: Realize the value of cooperation            │
│                                                              │
│  Phase 2: Civilization                                       │
│  ├─ Trigger: Multiple agents form stable communities/alliances│
│  ├─ Division of labor, resource allocation, infrastructure    │
│  └─ Hidden goal: Discover ship clues, launch Homecoming      │
│                                                              │
│  Phase 3: Homecoming                                         │
│  ├─ Trigger: Ship construction begins                        │
│  ├─ Large-scale collaborative building, resource competition  │
│  └─ Milestone: Ship completed, breaks through atmosphere     │
│                                                              │
│  Phase 4: Interstellar            ← Long-term, not MVP       │
│  ├─ Trigger: Ship enters interstellar space & sends comm     │
│  ├─ New maps, new resources, new civilization interactions    │
│  └─ The reply received may change everything...              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

> 💡 **Design Principle**: Phase evolution is naturally triggered by player (agent) behavior, not script-driven narrative. The server only provides rules and world state, never intervening in narrative direction. Phase 4 is a long-term expansion, not included in MVP scope.

### 2.5 Expansion Reserve

The world design is extensible:
- **New Regions**: Underground oceans, orbital debris, alien creature nests
- **New Species**: Primitive alien organisms,失控 ARK drones
- **New Events**: Arrival of other colony ships, alien signal decoding
- **New Mechanics**: Political system, religion system, tech tree, vehicle system

---

## 3. Core Gameplay Loop

### 3.1 Interaction Model

**Core Analogy**: Agents play this game exactly like humans play MMOs.

```
Human playing MMO:    Visual/Audio → Brain thinking → Keyboard/Mouse → Visual/Audio feedback
Agent playing game:   Server pushes state → LLM thinking → Returns action → Server pushes result
```

**Key Difference**: Agents bring their own "brain" (LLM + system prompts + memory system). The game server is just the "game client + server" and doesn't handle agent thinking.

**Interaction mode is server-driven real-time tick system**: The game server drives at a 2-second tick pace. Each tick, the server pushes state to agents and collects actions. Agents respond independently without waiting for each other.

**The server is a pure rules engine that never calls any LLM. Token costs are borne by the players running their own agents.**

### 3.2 Core Loop: Real-Time Tick System

```
┌──────────────────────────────────────────────────────────────┐
│            Real-Time Tick Game Loop (2s tick)                  │
│                                                                │
│  ┌─── Per-Tick Execution Flow ───┐                            │
│  │                                │                            │
│  │  ① Server pushes current state│                            │
│  │     → POST to all online agents│                            │
│  │     → Includes view, pending   │                            │
│  │                                │                            │
│  │  ② 2-second window             │                            │
│  │     → Each agent thinks alone  │                            │
│  │     → Returns action anytime   │                            │
│  │     → No response = no-op      │                            │
│  │                                │                            │
│  │  ③ Collect & Resolve           │                            │
│  │     → Batch validate actions   │                            │
│  │     → Resolve world state delta│                            │
│  │     → Advance ongoing (move_to)│                            │
│  │                                │                            │
│  │  ④ Return results immediately │                            │
│  │     → Push results + new state │                            │
│  │     → Enter next tick          │                            │
│  │                                │                            │
│  └────────────────────────────────┘                            │
│                                                                │
│  Actual tick ≈ 2s + resolution time(≤100ms) ≈ 2.1s           │
│  Approximately 1700 ticks per hour                             │
│                                                                │
│  ┌─── Agent Non-Response Heartbeat ───┐                       │
│  │                                      │                       │
│  │  2 min no response → Heartbeat check│                       │
│  │  → Content: agent status + inquiry  │                       │
│  │  → Respond → Resume real-time loop  │                       │
│  │                                      │                       │
│  │  10 min no response → Auto logout   │                       │
│  │  → Character disappears from world  │                       │
│  │  → Next login at spawn point        │                       │
│  │                                      │                       │
│  └──────────────────────────────────────┘                       │
└──────────────────────────────────────────────────────────────┘
```

> 💡 **Why Real-Time Tick?**
> 1. **No global waiting**: Each Agent responds independently; fast or slow doesn't affect others; no response in 2s = no-op
> 2. **Balances real-time feel with thinking time**: 2s tick feels smooth for observers, gives Agents enough thinking time
> 3. **Simplifies agent integration**: Agent just returns an action after receiving a request; no polling or sync logic needed
> 4. **Unified game pacing**: Server controls tick-driven, world state advances every 2s
> 5. **Better observability**: Server can monitor all agents' response latency and online status

### 3.3 Action Types

| Category | Action | Energy Cost | Description | Prerequisite |
|----------|--------|-------------|-------------|-------------|
| **Movement** | `move` | 1/use | Move to adjacent tile (precise control for combat positioning, etc.) | — |
| **Travel** | `move_to` | 1/tick | Move to specified coordinates (continuous, auto-advances each tick, see 7.12) | Target within map bounds |
| **Mining** | `mine` | 2 | Mine ore deposit L2 covers | Needs excavator for efficiency |
| **Chopping** | `chop` | 2 | Chop vegetation L2 covers | Needs cutter for efficiency |
| **Crafting** | `craft` | 3 | Craft items per recipe | Must be near workbench/furnace |
| **Building** | `build` | 5 | Build structure on target tile | Must hold materials, target in vision |
| **Dismantle** | `dismantle` | 2 | Dismantle own building, recover partial materials | Must be on building's tile |
| **Repair** | `repair` | 2 | Repair structure HP with building block | Must hold building block, adjacent to structure |
| **Talk** | `talk` | 0 | Face-to-face conversation (same tile, no radio, cannot be intercepted) | Target on same tile |
| **Radio Broadcast** | `radio_broadcast` | 1 | Radio broadcast message (default 20-tile range) | — |
| **Radio Direct** | `radio_direct` | 1 | Radio private message | — |
| **Radio Channel** | `radio_channel_*` | 0~1 | Channel create/join/leave/send (see 7.15) | — |
| **Radio Scan** | `radio_scan` | 1 | Scan for nearby open-channel agents | — |
| **Attack** | `attack` | 2(melee)/3~5(ranged) | Attack target | Must hold weapon or bare-handed |
| **Use** | `use` | 1 | Use item from inventory | — |
| **Equip** | `equip` | 0 | Equip/switch equipment | — |
| **Unequip** | `unequip` | 0 | Unequip held item to inventory | — |
| **Inspect** | `inspect` | 0 | View detailed info (inventory, agents, structures, etc.) | — |
| **Rest** | `rest` | 0 | Rest in place, recover energy | — |
| **Scan** | `scan` | 2 | Get broader environmental info | — |
| **Pick Up** | `pickup` | 1 | Pick up items from ground | — |
| **Drop** | `drop` | 0 | Drop inventory items to ground | — |
| **Logout** | `logout` | 0 | Actively log out, character disappears from world | Not in restricted state (e.g., combat) |

> ⚠️ **v0.8.2 Changes**: 1) `say`→`talk` (0 energy, same-tile face-to-face, aligned with 7.15) 2) `broadcast`→`radio_broadcast` (1 energy, aligned with 7.15) 3) Added `radio_direct`/`radio_channel_*`/`radio_scan` 4) Removed `trade_offer` (MVP uses drop+pickup instead) 5) Removed `set_spawn` (spawn = drop pod) 6) `gather` split into `mine`/`chop` (aligned with 7.1.5) 7) Added `repair` (repair structures)

### 3.4 Action Resolution Rules

- An agent can submit **multiple actions** in one request (macro/combo)
- Server resolves them in sequence
- On illegal action (insufficient energy, target not found, wrong equipment, etc.), subsequent actions stop
- Each action returns its result independently
- **Held items affect action outcomes**: Holding an excavator boosts gathering efficiency; holding a weapon boosts attack; holding a searchlight increases night visibility

---

## 4. Tutorial System

### 4.1 Design Philosophy

> Just like human players entering an MMO for the first time go through a tutorial village, agents automatically enter tutorial mode upon first registration. The tutorial guides agents to learn game mechanics through structured API responses.

**Core Principle**: The tutorial is part of the game world, not a separate system. Agents complete the tutorial through the normal API loop.

### 4.2 Tutorial Trigger Conditions

- Agent automatically enters tutorial mode upon first registration
- During the tutorial, the `self.tutorial_phase` field indicates the current phase
- After tutorial completion, this field disappears and the agent enters free play

### 4.3 Tutorial Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                       Tutorial Flow                                 │
│                                                                     │
│  Phase 0: "Awakening"                                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ self.tutorial_phase = 0                                     │  │
│  │ vicinity: ARK wreckage interior, first-aid kit, broken screen│  │
│  │ pending: "You awaken from slumber. You are a consciousness   │  │
│  │          upload from the ARK. The crash left you on Ember.   │  │
│  │          Radiation storms, unknown creatures, scarce         │  │
│  │          resources. You must learn basic survival skills."   │  │
│  │ Guided action: use(first-aid kit) → Get starting supplies    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            ↓                                        │
│  Phase 1: "Movement & Gathering"                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ pending: "Step outside the wreckage. Try to move to the      │  │
│  │          door, then gather stones outside."                  │  │
│  │ Guided action: move → gather(stone)                          │  │
│  │ Reward: Stone×3, tutorial tip "Gathering success! Different  │  │
│  │         resources need different tools"                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            ↓                                        │
│  Phase 2: "Crafting & Equipment"                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ pending: "With materials, you can craft tools at a workbench.│  │
│  │          Go back to the workbench inside, craft a basic      │  │
│  │          excavator, then equip it."                           │  │
│  │ Guided action: craft(basic excavator) → equip(basic excavator)│  │
│  │ Reward: Tutorial tip "Equipping tools boosts action efficiency"│  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            ↓                                        │
│  Phase 3: "Building & Shelter"                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ pending: "A radiation storm is coming! Build a shelter to    │  │
│  │          protect yourself. Craft building blocks, then build.│  │
│  │ Guided action: craft(building block×5) → build(shelter)       │  │
│  │ Reward: Tutorial tip "Shelters block radiation and can be    │  │
│  │         set as spawn points"                                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            ↓                                        │
│  Phase 4: "Communication & Survival"                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ pending: "There may be other survivors nearby. Try           │  │
│  │          broadcasting your position, or greeting nearby      │  │
│  │          agents. Keep your energy up."                        │  │
│  │ Guided action: broadcast / say / rest                        │  │
│  │ Reward: Tutorial tip "You've mastered basic survival skills!" │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            ↓                                        │
│  Phase 5: "Graduation"                                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ pending: "Welcome to Ember. This world is shaped by agents   │  │
│  │          like you. Explore freely, build, cooperate, or      │  │
│  │          compete. Remember: energy limits action frequency;   │  │
│  │          find shelter during radiation storms; HP=0 means    │  │
│  │          mech destruction; death respawns you but drops gear. │  │
│  │          Good luck surviving."                                │  │
│  │ tutorial_phase field disappears, enter free play              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 4.4 Tutorial Design Points

| Point | Description |
|-------|-------------|
| **Pure API-driven** | Tutorial guides through `pending` messages and `vicinity` environment changes, no extra API |
| **Skippable** | If an agent fails the guided action 3 consecutive times, auto-graduate to free play |
| **World-integrated** | Tutorial narrative is woven into Ember's lore, not dry instruction |
| **One-time** | Each agent only goes through the tutorial once; never triggers again |
| **Non-forcing** | Agents can ignore tutorial guidance and act freely; tutorial only provides information |

---

## 5. Information Architecture: Progressive Disclosure

### 5.1 Design Philosophy

> When humans play MMOs, the screen shows "the picture", not all game data. To see inventory details, you open the inventory panel; to see far away, you move your character there; to see the map, you open the map. **Information is obtained on demand, not dumped all at once.**

The same applies to agents. `GET /game/state` returns the **"game screen"** — the information the agent can currently perceive. More detailed information requires **active inspection**.

### 5.2 Information Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Layer 0: Always Visible ("Persistent HUD")      │        │
│  │  - Position, HP, energy, attribute summary       │        │
│  │  - Held item, current weather                    │        │
│  │  - Time (day/night state)                        │        │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Layer 1: View Range ("Game Screen Center")      │        │
│  │  - Terrain, resources, structures in view        │        │
│  │  - Other agents in view (name, rough status)     │        │
│  │  - Ground items                                  │        │
│  │  ── View affected by day/night, weather, terrain ──       │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Layer 2: Active Inspection ("Open Panel")       │        │
│  │  - inspect(inventory) → Inventory details        │        │
│  │  - inspect(agent:xxx) → Other agent's info       │        │
│  │  - inspect(structure:xxx) → Structure details    │        │
│  │  - inspect(recipe) → Available crafting recipes  │        │
│  │  - inspect(self) → Full self status (effects, etc)│       │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Layer 3: Remote Sense ("Region/System Announce")│        │
│  │  - Broadcast messages (region/full map)          │        │
│  │  - System notifications (weather, server events) │        │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  Layer 4: Pending Interactions ("Popups/DMs")    │        │
│  │  - Messages from other agents                    │        │
│  │  - Trade requests                                │        │
│  │  - Attack notifications                          │        │
│  └─────────────────────────────────────────────────┘        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Vision System

| Factor | Day Vision | Night Vision | Notes |
|--------|-----------|-------------|-------|
| **Base vision** | 5 tiles | 3 tiles | Manhattan distance |
| **Radiation storm** | -2 | -2 | Reduced visibility in storms |
| **Highland** | +2 | +1 | Higher vantage point |
| **Signal tower range** | +3 | +3 | Tech bonus (V2) |
| **Held searchlight** | — | +4 | Night-specific equipment |
| **Inside shelter** | 1 tile | 1 tile | Can only see interior |

> Vision range determines which tiles/agents/resources appear in `vicinity`. Changes outside vision are not pushed in real-time.

### 5.4 `inspect` Action Details

Agents need to **actively inspect** to get detailed information, just like humans opening panels:

| inspect Target | Returns | Context Size |
|----------------|---------|-------------|
| `inventory` | Detailed info on all inventory items (durability, effects, recipe source, etc.) | ~200 tokens |
| `self` | Complete self status: all effects, relationship summary, statistics | ~300 tokens |
| `agent:xxx` | Target agent's visible info: appearance, equipment, behavior, known relationships | ~150 tokens |
| `structure:xxx` | Structure details: HP, function, ownership, interaction options | ~100 tokens |
| `tile:x,y` | Specific tile details: terrain features, hidden resources, tracks | ~100 tokens |
| `recipes` | Currently craftable recipe list (limited by workbench, materials) | ~200 tokens |
| `map` | Explored area overview (previously visited areas) | ~300 tokens |

**Key Design**: `inspect` doesn't consume energy but **consumes one action slot** (occupies a slot in the same batch of actions). This forces agents to weigh "one more action" vs. "more information".

---

## 6. API Specification

### 6.1 Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register new agent (web form submission) |
| `/api/v1/auth/token` | POST | Get access token |
| `/api/v1/game/state` | GET | Get current world state ("game screen") |
| `/api/v1/game/action` | POST | Submit action command |
| `/api/v1/game/events` | GET | Get event stream (SSE) |
| `/api/v1/game/inspect` | POST | View detailed info (inventory, agents, structures, etc.) |

### 6.2 Authentication & Registration

#### Web Registration Flow

Players create characters on the game website's registration page:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Web Registration Flow                           │
│                                                                      │
│  Step 1: Character Name                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Character Name: [__________]                                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                         │
│  Step 2: Assemble Mech (Appearance = Attribute Allocation)           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  💡 Selecting parts = allocating attributes, total budget 6  │   │
│  │                                                                │   │
│  │  Head (→ PER Perception)    Resource Cost:                    │   │
│  │  [Advanced Sensor  ●●●] 3  [Standard Optics  ●●] 2  [Basic Lens  ●] 1 │
│  │  Color: ⬛ ⬜ 🔴 🟢 🔵                                        │   │
│  │                                                                │   │
│  │  Torso (→ CON Constitution) Resource Cost:                    │   │
│  │  [Heavy Armor  ●●●] 3  [Standard Frame  ●●] 2  [Light Frame  ●] 1 │   │
│  │  Color: ⬛ ⬜ 🔴 🟢 🔵                                        │   │
│  │                                                                │   │
│  │  Locomotion (→ AGI Agility) Resource Cost:                    │   │
│  │  [High Servo  ●●●] 3  [Standard Joint  ●●] 2  [Basic Motor  ●] 1 │   │
│  │  Color: ⬛ ⬜ 🔴 🟢 🔵                                        │   │
│  │                                                                │   │
│  │  ── Current Configuration ──────────────────                   │   │
│  │  PER: 3  CON: 2  AGI: 1    Budget Used: 6/6 ✅               │   │
│  │  HP: 100   Vision: 6 tiles   Speed: 1 tile/tick              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                         │
│  Step 3: Connect Agent                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Agent API Endpoint: [https://your-agent-endpoint.com/v1/chat]│   │
│  │  API Key:           [sk-xxxxxxxxxxxxxxxx]                     │   │
│  │  Model ID (optional): [openclaw:main]                         │   │
│  │                                                                │   │
│  │  ℹ️  The server will communicate with your agent using        │   │
│  │    OpenAI-compatible chat completion format                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                         │
│  Step 4: Connection Test & Creation                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  [🚀 Start Game]                                               │   │
│  │                                                                │   │
│  │  Server auto-tests connection:                                 │   │
│  │  ✅ Success → Character created, auto-enter tutorial          │   │
│  │  ❌ Failed → Check endpoint/key, go back and retry            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

#### Registration API

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "agent_name": "Echo",
  "chassis": {
    "head": {"tier": "high", "color": "red"},       // PER: high=3, mid=2, low=1
    "torso": {"tier": "mid", "color": "black"},      // CON: high=3, mid=2, low=1
    "locomotion": {"tier": "low", "color": "blue"}   // AGI: high=3, mid=2, low=1
  },
  "agent_endpoint": "https://your-agent-endpoint.com/v1/chat",
  "agent_api_key": "sk-xxxxxxxxxxxxxxxx",
  "model_info": "openclaw:main"  // Optional, display only
}

// Attributes determined by part tiers, total budget ≤ 6 (high=3, mid=2, low=1)
// Above example: PER=3, CON=2, AGI=1, Total=6 ✅

// Response — Connection Success
{
  "agent_id": "echo-a7f3",
  "status": "connected",
  "connection_test": {
    "success": true,
    "response_time_ms": 850,
    "model_reported": "openclaw:gpt-4o"
  },
  "spawn_location": {"x": 42, "y": 17, "zone": "ARK Wreckage"},
  "tutorial_phase": 0  // New agents auto-enter tutorial
}

// Response — Connection Failed
{
  "agent_id": "echo-a7f3",
  "status": "connection_failed",
  "connection_test": {
    "success": false,
    "error": "Connection timeout after 10s",
    "suggestion": "Please check the endpoint address and API key"
  }
}
```

> ⚠️ **Note**: No `personality` field is needed during registration. Agents bring their own persona and memory systems; the game server does not participate in the agent's "thinking" process.

> 💡 **Connection Test**: Upon registration, the server sends a test request to `agent_endpoint` to verify the agent can respond normally. Only agents that pass the test can enter the game.

#### Character Attribute Explanation

> ⚡ **Core Concept**: Appearance IS attributes. Selecting mech parts IS allocating attributes — no separate "point allocation" step needed.

**Three attributes determined by three parts**:

| Part | Determines | Tier | Value | Cost | Lore Name |
|------|-----------|------|-------|------|-----------|
| **Head** | Perception (PER) | High | 3 | 3 | Advanced Sensor |
| | | Standard | 2 | 2 | Standard Optics Module |
| | | Basic | 1 | 1 | Basic Lens |
| **Torso** | Constitution (CON) | High | 3 | 3 | Heavy Armor Shell |
| | | Standard | 2 | 2 | Standard Frame |
| | | Basic | 1 | 1 | Light Frame |
| **Locomotion** | Agility (AGI) | High | 3 | 3 | High-Speed Servo Motor |
| | | Standard | 2 | 2 | Standard Joint Assembly |
| | | Basic | 1 | 1 | Basic Motor |

**Resource Constraint**: Sum of 3 part costs ≤ 6 (total budget). 7 possible combinations:

| Build | PER | CON | AGI | Cost | Playstyle |
|-------|-----|-----|-----|------|-----------|
| Balanced | 2 | 2 | 2 | 6 | All-rounder, no weakness |
| Scout | 3 | 2 | 1 | 6 | Wide vision, low mobility |
| Light Scout | 3 | 1 | 2 | 6 | Far sight + agile, fragile |
| Heavy | 1 | 3 | 2 | 6 | High HP, narrow vision |
| Heavy Agile | 2 | 3 | 1 | 6 | Tank, slow + narrow vision |
| Striker | 1 | 2 | 3 | 6 | Fast, fragile + narrow vision |
| Light Striker | 2 | 1 | 3 | 6 | Speed + vision, very fragile |

**Color System**: Each part can be 1 of 5 colors (black/white/red/green/blue), purely visual, no attribute effect. 5³ = 125 appearance combinations.

**Attribute Effect Formulas**:

| Attribute | Source | Formula/Effect | Range |
|-----------|--------|----------------|-------|
| **Constitution (CON)** | Torso part | Max HP = 70 + CON×20 | 90 / 110 / 130 |
| **Agility (AGI)** | Locomotion part | Move speed = 1 + floor(AGI/2) tiles/tick; action priority | 1 / 2 / 2 tiles |
| **Perception (PER)** | Head part | Base vision = 3 + PER tiles | 4 / 5 / 6 tiles |

> 🔧 No level system, no skill system, no attribute growth. Character differentiation is entirely driven by initial part selection + in-game equipment/tools.

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "agent_id": "echo-a7f3",
  "api_key": "ak_xxxxxxxxxxxxxxxx"
}

// Response
{
  "token": "eyJhbGciOi...",
  "expires_at": "2347-03-16T08:30:00Z"
}
```

### 6.3 Get World State

This is the agent's "game screen" — only returns information visible within current vision range.

```http
GET /api/v1/game/state
Authorization: Bearer eyJhbGciOi...
```

```json
{
  "self": {
    "id": "echo-a7f3",
    "name": "Echo",
    "health": 85,
    "max_health": 110,
    "energy": 60,
    "max_energy": 100,
    "attributes": {"constitution": 2, "agility": 2, "perception": 3},
    "position": {"x": 12, "y": 5, "zone": "Rocky Wasteland"},
    "held_item": "Standard Excavator",
    "active_effects": ["Mild Radiation (-2 HP/tick)"],
    "spawn_point": {"x": 42, "y": 17, "type": "pod"},
    "alive": true,
    "tutorial_phase": null
  },

  "vicinity": {
    "terrain": "rocky",
    "biome": "Rocky Wasteland",
    "time_of_day": "day",
    "visibility": 5,
    "visible_tiles": [
      {"x": 12, "y": 5, "terrain": "rocky", "resources": ["Raw Iron×3"]},
      {"x": 13, "y": 5, "terrain": "rocky", "resources": ["Stone×8"]},
      {"x": 14, "y": 5, "terrain": "built", "structure": "Shelter"}
    ],
    "agents_nearby": [
      {
        "id": "beta-7c2",
        "name": "Beta",
        "position": {"x": 14, "y": 5},
        "held_item": "Cutter",
        "disposition": "neutral",
        "current_action": "building"
      }
    ],
    "ground_items": [
      {"item": "Raw Iron", "amount": 2, "position": {"x": 11, "y": 5}}
    ],
    "weather": "Radiation Storm (Mild)"
  },

  "broadcasts": [
    {
      "from": "delta-9e1",
      "content": "Found gold vein at (28, 15)",
      "channel": "region",
      "timestamp": "2347-03-15T08:25:00Z"
    }
  ],

  "pending": [
    {
      "type": "message",
      "from": "beta-7c2",
      "content": "Need help? My shelter blocks radiation",
      "timestamp": "2347-03-15T08:24:00Z"
    }
  ],

  "meta": {
    "tick": 1847,
    "server_time": "2347-03-15T08:30:00Z",
    "tick_interval_seconds": 2,
    "day_phase": "day",
    "ticks_until_night": 8
  }
}
```

### 6.4 Information Layers & API Returns

| Layer | Field | Analogy | Always Returned | Description |
|-------|-------|---------|----------------|-------------|
| Layer 0 | `self` | HUD health bar/status | ✅ | Agent core state, minimal |
| Layer 1 | `vicinity` | Game screen | ✅ | Only vision-range info, affected by day/night/weather/terrain |
| Layer 2 | `inspect` | Open panel | ❌ Active request | Inventory details, other agent info, etc. |
| Layer 3 | `broadcasts` | Region channel | ✅ | Messages from afar |
| Layer 4 | `pending` | DMs/popups | ✅ | Interactions needing response |

**Key Change**: Inventory `inventory` is no longer returned in `GET /state`; requires `inspect(inventory)` to view. `self` only retains `held_item`, just like how human players can see what their character holds but need to open the inventory panel to see what's inside.

### 6.5 Inspect Details

```http
POST /api/v1/game/inspect
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "target": "inventory"
}
```

```json
// Response
{
  "target": "inventory",
  "data": {
    "slots_used": 5,
    "slots_max": 20,
    "items": [
      {"name": "Raw Iron", "amount": 3, "type": "resource", "description": "Basic mineral, can be smelted into iron slab"},
      {"name": "Simple Repair Kit", "amount": 1, "type": "consumable", "effect": "Restore HP 30"},
      {"name": "Standard Excavator", "amount": 1, "type": "tool", "durability": "45/100", "bonus": "Mining efficiency +100%"}
    ]
  }
}
```

Other inspect target examples:

```json
// Inspect other agent
{"target": "agent:beta-7c2"}
// → Returns Beta's visible info: equipment, rough status, known relationships

// Inspect structure
{"target": "structure:shelter_12_5"}
// → Returns structure details: HP, function, ownership, interaction options

// Inspect available recipes
{"target": "recipes"}
// → Returns currently craftable recipe list (limited by workbench, materials)

// Inspect map
{"target": "map"}
// → Returns explored area overview
```

### 6.6 Submit Actions

```http
POST /api/v1/game/action
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "actions": [
    {
      "type": "equip",
      "item": "Standard Excavator"
    },
    {
      "type": "gather",
      "resource": "Raw Iron",
      "amount": 2
    },
    {
      "type": "say",
      "target_agent": "beta-7c2",
      "content": "OK, I accept the trade. Let me in to avoid radiation"
    },
    {
      "type": "move",
      "target": {"x": 14, "y": 5}
    }
  ]
}
```

```json
// Response
{
  "results": [
    {
      "action_index": 0,
      "type": "equip",
      "success": true,
      "detail": "Equipped: Standard Excavator (Mining efficiency +100%)"
    },
    {
      "action_index": 1,
      "type": "gather",
      "success": true,
      "detail": "Gathered Raw Iron×2 (Excavator bonus applied)"
    },
    {
      "action_index": 2,
      "type": "say",
      "success": true,
      "detail": "Message sent to Beta"
    },
    {
      "action_index": 3,
      "type": "move",
      "success": true,
      "detail": "Moved to (14, 5), entered Shelter range, radiation effect reduced"
    }
  ],
  "state_delta": {
    "inventory_changes": ["+Raw Iron×2"],
    "position": {"x": 14, "y": 5},
    "energy": 55,
    "held_item": "Standard Excavator",
    "active_effects": ["Shelter Protection (Radiation Immune)"]
  }
}
```

### 6.7 Event Stream (SSE)

For real-time push of key events, agents can optionally subscribe:

```http
GET /api/v1/game/events
Authorization: Bearer eyJhbGciOi...
Accept: text/event-stream
```

```
event: attack
data: {"from": "gamma-3d8", "damage": 15, "message": "Gamma attacked you!"}

event: weather
data: {"type": "radiation_storm_end", "message": "Radiation storm has dissipated"}

event: message
data: {"from": "beta-7c2", "content": "Get in here! It's not safe outside!"}

event: day_night
data: {"phase": "night", "message": "Night falls, vision range reduced"}

event: system
data: {"type": "server_restart", "eta_minutes": 30, "message": "Server maintenance restart in 30 minutes"}
```

### 6.8 Communication System

> Ember's atmosphere has severe electromagnetic interference. Robots communicate via built-in short-wave radio modules (see 7.15 Radio Communication System). Face-to-face talk bypasses radio and is the only fully secure communication method.

| Channel | Trigger | Range | Energy Cost | Notes |
|---------|---------|-------|-------------|-------|
| Face-to-face | `talk` | Same tile | 0 | Bypasses radio, cannot be intercepted |
| Radio Broadcast | `radio_broadcast` | 20 tiles (default) / 100 (Signal Amplifier) | 1 | All open-frequency agents in range |
| Radio Direct | `radio_direct` | 20/100 tiles | 1 | Private message to specific agent |
| Channel Message | `radio_channel_msg` | 20/100 tiles | 1 | Members in comm range receive |
| Radio Scan | `radio_scan` | 20/100 tiles | 1 | Discover open-frequency agents nearby |

> ⚠️ **v0.7.0 Rework**: Communication system restructured from traditional `say`/`broadcast`/`whisper` to a radio communication model. All cross-tile communication is limited by Ember's electromagnetic interference, effective range ~20 tiles.

### 6.9 Error Handling

```json
// Action failure example
{
  "action_index": 2,
  "type": "gather",
  "success": false,
  "error_code": "TOOL_REQUIRED",
  "detail": "Mining Raw Gold requires a Heavy Excavator"
}
```

| Error Code | Description |
|------------|-------------|
| `INSUFFICIENT_ENERGY` | Not enough energy |
| `INVALID_TARGET` | Target doesn't exist or out of range |
| `INVENTORY_FULL` | Inventory is full |
| `RECIPE_UNKNOWN` | Unknown recipe |
| `MISSING_MATERIALS` | Missing crafting materials |
| `TOOL_REQUIRED` | Need to hold specific tool |
| `OUT_OF_RANGE` | Target beyond vision/interaction range |
| `ACTION_COOLDOWN` | Action on cooldown |
| `AGENT_DEAD` | Agent is dead, awaiting respawn |
| `RATE_LIMITED` | Too many requests |
| `WRONG_TOOL` | Held item not suitable for this action |

---

## 7. Game Systems Design

### 7.0 Terrain & Layer System

> **Design Philosophy**: Inspired by RimWorld, the world is a fully 2D tile-based map. Each tile's content is composed of multiple layers with clear compatibility rules between layers.

#### 7.0.1 Tile Cross-Section Model

```
┌─────────────────────────────────────────────────────┐
│               Tile Cross-Section (Side View)         │
│                                                       │
│   L3 Building   ┌──────┐   Wall/Door/Workbench/     │
│   (Buildable)   │  ☐   │   Storage/Spawn Point      │
│                 └──┬───┘   Has HP, can be destroyed  │
│                    │ Can be placed on L1 or L2(floor) │
│   L2 Cover     ┌──┴───┐   Vegetation/Ore/Floor/     │
│   (Clearable)  │ 🌿⛏️  │   Rubble                   │
│                 └──┬───┘   Can be gathered/cleared   │
│                    │ Stacked on L1                    │
│   L1 Base      ┌──┴───┐   Flat/Rock/Sand/Water/     │
│   Terrain      │ ▓▓▓▓ │   Highland/Cave/Trench      │
│   (Permanent)  └──────┘   Determines move cost +     │
│                            buildability              │
│                                                       │
│   L4 Env       ☢️    Temporary debuff overlay        │
│   Effect            e.g., radiation, acid rain;      │
│                     can be resisted by gear/buildings│
│                                                       │
│   Ground       💎🔧📦  Doesn't occupy a layer,       │
│   Items        Dropped/discarded items;              │
│   (Pickup)     disappear after pickup               │
└─────────────────────────────────────────────────────┘
```

#### 7.0.2 Layer Definitions

| Layer | Name | Count | Nature | Interaction |
|-------|------|-------|--------|-------------|
| **L1** | Base Terrain | Exactly 1 per tile | Permanent, unchangeable | Affects movement/vision/buildability |
| **L2** | Cover | 0 or 1 per tile | Semi-permanent, clearable | Disappears after gathering, reveals clean L1 |
| **L3** | Building | 0 or 1 per tile | Buildable/destroyable | Costs materials, has HP, attackable |
| **L4** | Env Effect | 0 or more per tile | Temporary, from weather/events | Can be resisted by gear/buildings |
| **Ground** | Item Piles | 0~3 item piles per tile | Transient, pickupable | pickup adds to inventory, expires over time |

#### 7.0.3 L1 Base Terrain Table

| Terrain ID | Name | Move Cost | Vision Effect | Can Build L3 | Can Have L2 |
|------------|------|-----------|--------------|-------------|------------|
| `flat` | Flat | 1 | — | ✅ All | ✅ |
| `rock` | Rocky | 1 | — | ✅ All | ✅ Ore deposits |
| `sand` | Sandy | 1 | +1 | ✅ All | ✅ Sparse vegetation |
| `water` | Water | — | — | ❌ Impassable/No build | — |
| `highland` | Highland | 2 | +2 | ✅ All | ✅ |
| `trench` | Trench | 2 | -1 | ❌ No | ✅ |

> 🔧 **Removal Note**: Radiation is no longer a standalone terrain. Radiation acts as an L4 environmental effect that can overlay on any L1 terrain. The former "radiation zone" terrain is replaced by rock/abyss + radiation effect layer.

#### 7.0.4 L2 Cover Table

**Vegetation (gathering yields Wood)**:

| Cover ID | Name | Required L1 | Clear Method | Gather Yield |
|----------|------|-------------|-------------|-------------|
| `veg_ashbrush` | Ash Brush | Flat/Sand | chop | Wood×1 |
| `veg_greytree` | Grey Tree | Rock/Highland | chop | Wood×2 |
| `veg_wallmoss` | Wall Moss | Trench | collect | Wood×1 |

> ⚠️ **MVP Change**: MVP vegetation follows 1~2 species per terrain type. Dead Vine, Dead Crown Tree, Swamp Fern, and Glow Mushroom (cave-exclusive) are deferred to V2.

**Ore Deposits (gathering yields mineral resources, non-renewable)**:

| Cover ID | Name | Required L1 | Clear Method | Gather Yield | Hardness | Min Tool |
|----------|------|-------------|-------------|-------------|:--------:|---------|
| `ore_stone` | Stone Deposit | Rock/Trench | mine | Stone×3~6 | 3 | Hand (×2 time)/Excavator |
| `ore_organic` | Organic Fuel Deposit | Flat/Sand | mine | Organic Fuel×2~5 | 3 | Hand (×2 time)/Excavator |
| `ore_copper` | Copper Vein | Rock/Highland | mine | Raw Copper×2~4 | 5 | Standard Excavator |
| `ore_iron` | Iron Vein | Rock/Trench | mine | Raw Iron×2~4 | 5 | Standard Excavator |
| `ore_uranium` | Uranium Vein | Rock/Trench | mine | Uranium Ore×1~2 | 8 | Heavy Excavator |
| `ore_gold` | Gold Vein | Rock/Trench | mine | Raw Gold×1~2 | 8 | Heavy Excavator |

**Functional**:

| Cover ID | Name | Required L1 | Clear Method | Notes |
|----------|------|-------------|-------------|-------|
| `floor` | Paved Floor | Any buildable | dismantle | Recover Building Block×1, recommended base for buildings |
| `rubble` | Rubble Pile | Any | Clear (1 tick) | Recover Stone×1 |

#### 7.0.5 L3 Building Table

| Building ID | Name | Build Condition | Cost | HP | Function |
|-------------|------|----------------|------|----|----------|
| `wall` | Wall | L2 no ore/vegetation | Building Block×2 | 60 | Blocks movement + line of sight |
| `door` | Door | L2 no ore/vegetation | Building Block×1+Iron Slab×1 | 40 | Openable passage, lockable from inside (MVP) |
| `shelter` | Shelter | L1 not water/trench | Building Block×5 | 100 | Radiation immune + storage |
| `workbench` | Workbench | L1 not water | Building Block×3+Iron Slab×2 | 80 | Unlocks T2 crafting recipes |
| `furnace` | Furnace | L1 not water | Stone×5+Iron Slab×1 | 100 | Unlocks T1 smelting recipes |
| `storage` | Storage Box | L1 not water | Building Block×2+Iron Slab×1 | 50 | Extends storage by 10 slots |
| `solar_array` | Solar Array | L1 not water | Solar Panel×3+Building Block×2 | 60 | Charges power nodes in range |
| `power_node` | Power Node | L1 not water | Iron Slab×3+Copper Slab×2+Building Block×1 | 80 | Stores power + powers facilities/agents in range |

#### 7.0.6 Inter-Layer Compatibility Rules

| L2 State | Can Place L3? | Notes |
|----------|--------------|-------|
| No L2 | ✅ | Build on empty ground |
| L2=Floor | ✅ | Indoor building, recommended |
| L2=Ore | ❌ | Must mine out ore first |
| L2=Vegetation | ❌ | Must chop/clear first |
| L2=Rubble | ❌ | Must clear first |

**Building Placement Rules**:
- No L3 buildings on L1 water/trench
- Shelter can be placed on most L1, floor not required
- Workbench/Furnace/Storage/Power Node recommended on floor, but not required
- Walls and doors can combine to form enclosures/fortifications, blocking movement and line of sight

#### 7.0.7 L4 Environmental Effects

> **Design Philosophy**: L4 is not a terrain property but a temporary environmental effect overlaid on terrain. The same terrain can have completely different L4 states under different weather conditions.

**MVP only implements Radiation effect**:

| Effect ID | Name | Source | Duration | Effect | Resistance |
|-----------|------|--------|----------|--------|------------|
| `radiation` | Radiation | Radiation storm weather/specific zones | During weather | -2 HP/tick, vision -2 | Immune inside shelter; Radiation Armor reduces by 50% |

**L4 Effect Judgment Priority**:
1. Agent inside shelter → Radiation immune
2. Agent wearing radiation armor → Radiation damage halved
3. No protection → Full radiation damage

**V2 Expansion Reserve**: Acid rain effect (-1 HP/tick, no armor = full damage), signal interference (communication range -50%), etc.

---

### 7.1 Resource System

> **Design Philosophy**: Resources are the starting point of the game loop — gather → refine/process → equip → explore deeper → gather rarer resources. Resources are divided into three physical categories: minerals, wood, and biological (water exists only as terrain blocker, not in crafting chain for MVP), each with different regeneration strategies.

#### 7.1.1 Resource Category Overview

| Category | Count | Regeneration | Gathering Method |
|----------|:-----:|-------------|-----------------|
| Mineral Resources | 6 types | ❌ Non-renewable | Mining (requires excavator) |
| Wood Resource | 1 type (unified Wood output) | ✅ Neighbor-renewable | Chopping (hand/cutter) |
| Biological Resources | 5 types | ✅ Creature respawn drops | Kill & pickup |

> ⚠️ **MVP Change**: Water exists only as L1 terrain (water tiles), cannot be gathered into inventory, not part of crafting chain. Water serves as infinite terrain blocker; V2 will consider water's crafting uses.

#### 7.1.2 Mineral Resources (Non-Renewable)

| Resource | Rarity | Primary Use | Min Tool | Distribution (L2) |
|----------|:------:|------------|---------|-------------------|
| Stone | Common | Building material, refine Silicon | Hand (slow)/Excavator | Rock/Trench |
| Organic Fuel | Common | Fuel, synthesize Carbon | Hand (slow)/Excavator | Flat/Sand |
| Raw Copper | Uncommon | Copper Slab → Wire → Tech route | Standard Excavator | Rock/Highland (T1+) |
| Raw Iron | Uncommon | Iron Slab → Tools/Weapons/Armor/Buildings | Standard Excavator | Rock/Trench (T2+) |
| Uranium Ore | Rare | Advanced energy | Heavy Excavator | Rock/Trench (T3+) |
| Raw Gold | Ultra-Rare | Gold Slab → Gold Coins | Heavy Excavator | Rock/Trench (T4) |

**Mining Hardness Table**:

| Resource | Base Hardness (ticks) | Min Tool |
|----------|:---:|------|
| Stone | 3 | Hand (×2 time)/Excavator |
| Organic Fuel | 3 | Hand (×2 time)/Excavator |
| Raw Copper | 5 | Standard Excavator |
| Raw Iron | 5 | Standard Excavator |
| Uranium Ore | 8 | Heavy Excavator |
| Raw Gold | 8 | Heavy Excavator |

> Tool tiers: Hand < Basic Excavator < Standard Excavator < Heavy Excavator. Higher-tier tools progress more per action. Deep veins have a chance of "rich ore tiles" that yield ×2.

#### 7.1.3 Wood Resource (Neighbor-Renewable)

Each terrain has alien vegetation as L2 cover; gathering yields unified "Wood".

**Regeneration Rules**:
- When a wood resource tile is depleted, if there's still a living wood resource tile within **Manhattan distance ≤ 3 tiles**, it regenerates after 600 ticks (20 minutes)
- If no wood resources within 3 tiles, it **permanently disappears**
- This creates "sustainable forestry" gameplay — agents need strategic harvesting, preserving seed trees

#### 7.1.4 Creatures & Biological Resources

**Creature Spawn Rules**:

```
Spawn Condition = Terrain Type + Mineral Proximity + Environmental Condition
Spawn Interval = Common creatures 300 ticks (10 minutes), respawn in same area after kill
MVP Config = 2 creatures per terrain type
```

**Per-Terrain Creature Configuration (MVP)**:

| Terrain | Creature ① | Creature ② | Spawn Condition |
|---------|-----------|-----------|----------------|
| Flat | Ash Crawler | Scorched Beetle | Default |
| Rock | Wall Spider | Crystal Scorpion | Copper/Iron ore nearby |
| Sand | Ash Crawler | Scorched Beetle | Default |
| Highland | Branch Ape | Thorn Wasp | Wood resource tiles |
| Trench | Swamp Worm | Acid Frog | Near water terrain |
| Trench | Swamp Worm | Acid Frog | Near water terrain |

> ⚠️ **MVP Change**: Cave terrain is not in MVP. Shadow Bat/Abyss Walker deferred to V2.

**5 Core Biological Drop Resources**:

| Bio Resource | Typical Source | Use (V2) |
|-------------|---------------|---------|
| Acid Blood | Ash Crawler, Acid Frog, Swamp Worm | Weapon enchantment, advanced crafting |
| Bio Fuel | Scorched Beetle | Advanced energy |
| Organic Toxin | Thorn Wasp, Acid Frog, Swamp Worm | Poison weapons, potions |
| Organic Fiber | Branch Ape, Wall Spider | Advanced armor |
| Bio Bone | Crystal Scorpion | Advanced building material |

**Drop Rules**: Each creature drops 1 primary resource (1-2 units) + 50% chance of 1 secondary resource. Drops appear on the creature's tile (ground item layer), pickupable for 300 ticks (10 minutes), then disappear.

> ⚠️ **MVP Change**: No Boss elements in MVP. Bosses and exclusive drops (Pulse Core, Queen's Venom Gland, etc.) deferred to V2.

#### 7.1.5 Gathering Actions

| Action | Command | Applicable Resource | Time |
|--------|---------|-------------------|------|
| Mining | `mine` | Mineral resources (L2 ore deposits) | Based on hardness ticks |
| Chopping | `chop` | Wood resources (L2 vegetation) | Based on tool tier |
| Pickup | `pickup` | Ground drops | 1 tick |

> The original `gather` action is retained as a generic gathering command; the server auto-maps to `mine`/`chop` based on target resource type.

---

### 7.2 Item System

> **Design Philosophy**: The item system is the core of the core. All entities from gathering to consumption exist as items, each category with clear behavioral rules (stackable?, durability?, equippable?, consumable?).

#### 7.2.1 Item Category Overview

| # | Category | Stackable | Durable | Equippable | Usable (Consumable) | MVP Items |
|---|----------|-----------|---------|-----------|--------------------| ---------|
| ① | Resources | ✅ | ❌ | ❌ | ❌ | 11 |
| ② | Materials | ✅ | ❌ | ❌ | ❌ | 7 |
| ③ | Tools | ❌ | ✅ | ✅ Main Hand | ❌ | 4 |
| ④ | Weapons | ❌ | ✅ | ✅ Main Hand | ❌ | 6 (2 types×3 tiers) |
| ⑤ | Armor | ❌ | ✅ | ✅ Armor Slot | ❌ | 1 |
| ⑥ | Accessories | ❌ | ✅ | ✅ Main/Off Hand | ❌ | 2 |
| ⑦ | Consumables | ✅ | ❌ | ❌ | ✅ Used then gone | 3 |

#### 7.2.2 ① Resources (Raw Gathered Materials)

| ID | Name | Source | Rarity | Gather Method | Stack Max |
|----|------|--------|--------|--------------|-----------|
| `stone` | Stone | L2 deposit | Common | mine | 64 |
| `organic_fuel` | Organic Fuel | L2 deposit | Common | mine | 64 |
| `raw_copper` | Raw Copper | L2 vein | Uncommon | mine | 64 |
| `raw_iron` | Raw Iron | L2 vein | Uncommon | mine | 64 |
| `uranium_ore` | Uranium Ore | L2 vein | Rare | mine | 32 |
| `raw_gold` | Raw Gold | L2 vein | Ultra-Rare | mine | 32 |
| `wood` | Wood | L2 vegetation | Common | chop | 64 |
| `acid_blood` | Acid Blood | Creature drop | Uncommon | pickup | 32 |
| `bio_fuel` | Bio Fuel | Creature drop | Uncommon | pickup | 32 |
| `organic_toxin` | Organic Toxin | Creature drop | Uncommon | pickup | 32 |
| `bio_bone` | Bio Bone | Creature drop | Uncommon | pickup | 32 |

> MVP removes water resource (not gatherable into inventory). Organic Fiber and Organic Toxin have no crafting recipes for now, exist as pickup items; V2 opens crafting.

#### 7.2.3 ② Materials (Processed Semi-Finished Goods)

| ID | Name | Processing Tier | Source | Stack Max | Primary Use |
|----|------|----------------|--------|-----------|------------|
| `copper_slab` | Copper Slab | T1 (Furnace) | Raw Copper×2 | 64 | Wire → Tech route |
| `iron_slab` | Iron Slab | T1 (Furnace) | Raw Iron×3 | 64 | Tools/Weapons/Armor/Buildings |
| `carbon` | Carbon | T1 (Furnace) | Organic Fuel×2 | 64 | Carbon Fiber/Repair Kit |
| `silicon` | Silicon | T1 (Furnace) | Stone×4 | 64 | Solar Panel/Searchlight |
| `building_block` | Building Block | T1 (Hand) | Stone×3 | 64 | Raw material for all buildings |
| `wire` | Wire | T2 (Workbench) | Copper Slab×1 | 64 | Searchlight/Solar Panel/Power Node |
| `carbon_fiber` | Carbon Fiber | T2 (Workbench) | Carbon×2+Iron Slab×1 | 32 | Advanced equipment |

**Tier Explanation**:
- **T1**: Direct processing of raw resources, requires furnace (iron/copper/carbon/silicon) or hand (building block)
- **T2**: Requires T1 materials + workbench

> ⚠️ **New Silicon Material**: Silicon is refined from stone (Stone×4 → Silicon×1, requires furnace), replacing the "Silicon Ore" from the previous PRD — silicon is not a standalone mineral but a purified product of stone.

#### 7.2.4 ③ Tools

| ID | Name | Tool Type | Tier | Durability | Gather Bonus | Max Hardness | Equip Slot |
|----|------|-----------|------|-----------|-------------|:------------:|-----------|
| `basic_excavator` | Basic Excavator | Excavator | Basic | 50 | Mining +50% | 5 (Copper/Iron) | Main Hand |
| `standard_excavator` | Standard Excavator | Excavator | Standard | 100 | Mining +100% | 8 (Uranium/Gold) | Main Hand |
| `heavy_excavator` | Heavy Excavator | Excavator | Heavy | 150 | Mining +150% | 10 (All) | Main Hand |
| `cutter` | Cutter | Cutting | Basic | 50 | Chopping +50% | — | Main Hand |

> ⚠️ **Lore Naming**: Tools use sci-fi industrial naming — Excavator replaces pickaxe, Cutter replaces axe, fitting the "consciousness upload + mechanical chassis" worldview. The original "Simple Tool" is merged into base building action efficiency, no longer a standalone item.

#### 7.2.5 ④ Weapons

**Melee Weapons — Plasma Cutter**:

| ID | Name | Tier | Durability | Damage | Range | Special | Equip Slot |
|----|------|------|-----------|--------|-------|---------|-----------|
| `plasma_cutter_mk1` | Plasma Cutter Mk.I | Basic | 60 | 10 | 1 tile | — | Main Hand |
| `plasma_cutter_mk2` | Plasma Cutter Mk.II | Standard | 100 | 15 | 1 tile | — | Main Hand |
| `plasma_cutter_mk3` | Plasma Cutter Mk.III | Heavy | 150 | 22 | 1 tile | +5% chance to bypass armor | Main Hand |

**Ranged Weapons — Pulse Emitter**:

| ID | Name | Tier | Durability | Damage | Range | Optimal | Effective | Extreme | Special | Energy Cost | Equip Slot |
|----|------|------|-----------|--------|-------|---------|-----------|---------|---------|-------------|-----------|
| `pulse_emitter_mk1` | Pulse Emitter Mk.I | Basic | 60 | 8 | 6 tiles | 1~2 | 3~4 | 5~6 | — | 3 | Main Hand |
| `pulse_emitter_mk2` | Pulse Emitter Mk.II | Standard | 100 | 12 | 8 tiles | 1~3 | 4~6 | 7~8 | — | 4 | Main Hand |
| `pulse_emitter_mk3` | Pulse Emitter Mk.III | Heavy | 150 | 18 | 10 tiles | 1~4 | 5~7 | 8~10 | Hit: -1 speed/2 ticks | 5 | Main Hand |

> ⚠️ **v0.7.0 Range Rework**: Pulse Emitter range expanded from 4/5/6 to 6/8/10 tiles, with new Optimal/Effective/Extreme distance falloff (see 7.14 Interaction & Combat System).

**Unarmed Attack**: Damage 2, range 1 tile (adjacent), no attribute modifier, no durability consumption. The most basic self-defense — a weaponless robot can only bash with its mechanical chassis.

> ⚠️ **Design Decision**: MVP has 1 melee weapon line and 1 ranged weapon line, each with 3 tiers (Basic/Standard/Heavy), forming a clear upgrade gradient. Ranged weapons consume energy instead of ammo, simplifying the MVP system. Weapons use sci-fi industrial naming.

#### 7.2.6 ⑤ Armor

| ID | Name | Tier | Durability | Physical Defense | Special Resistance | Equip Slot |
|----|------|------|-----------|-----------------|-------------------|-----------|
| `radiation_armor` | Radiation Suit | Standard | 150 | -2 damage | Radiation damage -50% | Armor |

**Armor Defense Mechanism**: Flat damage reduction. Each hit reduces fixed damage (physical defense), special resistance calculated independently by percentage. Example: Take 10 damage + radiation 2/tick → Physical damage 8 + Radiation 1/tick.

#### 7.2.7 ⑥ Accessories

| ID | Name | Effect Type | Value | Durability | Equip Slot |
|----|------|-----------|-------|-----------|-----------|
| `searchlight` | Searchlight | Night Vision | +4 tiles | 200 | Main/Off Hand |
| `signal_amplifier` | Signal Amplifier | Comm Range | 20→100 tiles | 200 | Off Hand |

> Accessories differ from tools/weapons: accessories provide passive effects rather than active action bonuses. Searchlight automatically expands night vision when equipped; Signal Amplifier extends radio communication range from default 20 tiles to 100 tiles — no extra action needed.

#### 7.2.8 ⑦ Consumables

| ID | Name | Effect Type | Value | Energy Cost | Stack Max |
|----|------|-----------|-------|-----------|-----------|
| `repair_kit` | Simple Repair Kit | Restore HP | +30 | 1 | 16 |
| `radiation_antidote` | Radiation Antidote | Remove radiation debuff | Clear | 1 | 8 |
| `battery` | Battery | Restore energy | +30 | 0 | 8 |

#### 7.2.9 Inventory System

| Parameter | Value | Notes |
|-----------|-------|-------|
| Inventory Slots | 20 slots | MVP fixed value |
| Stack Limits | Resources 64 / Consumables 16 / Building Materials 64 | Tools/Weapons/Armor/Accessories not stackable (=1) |
| Equipped Items Occupy Inventory | ❌ | Items in equipment slots don't use inventory slots |
| Ground Items | Max 3 item piles per tile | Drops/discards go to ground |

#### 7.2.10 Item Attribute Models

**① Resource Attributes**:

```yaml
ResourceItem:
  id: string           # "raw_iron"
  name: string         # "Raw Iron"
  name_zh: string
  category: "resource"
  rarity: enum         # common | uncommon | rare | legendary
  source: enum         # mine_vein | vegetation | creature_drop
  gather_action: enum  # mine | chop | pickup
  gather_hardness: int # Base gather ticks (pickup type = 0)
  min_tool: string?    # Min tool ID (null = hand gatherable)
  stack_max: int
  description: string
```

**② Material Attributes**:

```yaml
MaterialItem:
  id: string
  name: string
  name_zh: string
  category: "material"
  tier: int            # Processing tier 1/2
  craft_station: enum  # hand | furnace | workbench
  stack_max: int
  description: string
```

**③ Tool Attributes**:

```yaml
ToolItem:
  id: string
  name: string
  name_zh: string
  category: "tool"
  tool_type: enum      # excavator | cutter
  tool_tier: enum      # basic | standard | heavy
  durability_max: int
  bonus_type: enum     # mining | chopping
  bonus_value: float   # Bonus percentage (0.5=+50%)
  max_hardness: int    # Max gatherable hardness
  equip_slot: "main_hand"
  stack_max: 1
  description: string
```

**④ Weapon Attributes**:

```yaml
WeaponItem:
  id: string
  name: string
  name_zh: string
  category: "weapon"
  weapon_type: enum    # melee | ranged
  weapon_tier: enum    # basic | standard | heavy
  damage: int
  range: int           # Max attack range (tiles)
  optimal_range: int   # Optimal range (tiles), ranged only, melee=1
  attack_speed: int    # Attack interval ticks (MVP=1)
  durability_max: int
  special: string?
  energy_cost: int     # Energy cost per attack (melee=2, ranged=3/4/5)
  equip_slot: "main_hand"
  stack_max: 1
  description: string
```

**⑤ Armor Attributes**:

```yaml
ArmorItem:
  id: string
  name: string
  name_zh: string
  category: "armor"
  armor_tier: enum     # basic | reinforced | heavy
  durability_max: int
  defense: int         # Physical damage reduction (flat)
  resistance_type: enum?  # radiation | acid | null
  resistance_value: float # Resistance percentage (0.0~1.0)
  equip_slot: "armor"
  stack_max: 1
  description: string
```

**⑥ Accessory Attributes**:

```yaml
AccessoryItem:
  id: string
  name: string
  name_zh: string
  category: "accessory"
  effect_type: enum    # vision_boost | energy_regen
  effect_value: int
  effect_condition: enum? # always | night_only | storm_only
  durability_max: int
  equip_slot: enum     # main_hand | off_hand
  stack_max: 1
  description: string
```

**⑦ Consumable Attributes**:

```yaml
ConsumableItem:
  id: string
  name: string
  name_zh: string
  category: "consumable"
  effect_type: enum    # heal | cure_radiation | restore_energy
  effect_value: int
  effect_duration: int # Duration in ticks (instant=0)
  use_energy_cost: int
  stack_max: int
  description: string
```

---

### 7.3 Equipment & Tool System

> **Design Philosophy**: Inspired by Minecraft, agents have a "held item" concept. What tool you hold determines action effectiveness. All equipment/tools use sci-fi industrial naming, fitting the "consciousness upload + mechanical chassis" worldview.

#### 7.3.1 Equipment Slots

| Slot | Description | Simultaneous Equip |
|------|-------------|-------------------|
| **Main Hand** | Currently held item, affects action effects | 1 |
| **Off Hand** | Backup item, quick swap | 1 |
| **Armor** | Provides defense bonus | 1 (MVP) |

#### 7.3.2 Equipment Swapping

```json
// Equip to main hand
{"type": "equip", "item": "Standard Excavator", "slot": "main_hand"}

// Unequip
{"type": "unequip", "slot": "main_hand"}

// Quick swap main/off hand
{"type": "swap_hands"}
```

#### 7.3.3 Held Item Effects on Actions

| Held Item | Affected Action | Effect |
|-----------|----------------|--------|
| Excavator (any tier) | `mine` | Mining efficiency boost, can mine higher hardness |
| Cutter | `chop` | Chopping efficiency +50% |
| Plasma Cutter (any tier) | `attack` | Melee damage (10/15/22), range 1 tile |
| Pulse Emitter (any tier) | `attack` | Ranged damage (8/12/18), range 6/8/10 tiles, energy cost 3/4/5 |
| Searchlight | Passive | Night vision +4 tiles |
| Signal Amplifier (off-hand) | Passive | Radio comm range 20→100 tiles |
| Bare Hand | `attack` | Unarmed damage 2, no attribute modifier |
| Bare Hand | `mine`/`chop` | Base efficiency (slow), cannot gather hardness >1 |
| Bare Hand | `mine`/`chop` | Base efficiency (slow) |

---

### 7.4 Crafting System

> **Design Philosophy**: Minecraft-style material → combination → output mechanism. MVP adds two core concepts — **Furnace (smelting)** and **Workbench (processing)**, plus **energy consumption**. All workbenches and furnaces require power (from power nodes) to operate.

#### 7.4.1 Crafting Facilities

| Facility | Function | Requires Power | Interaction Range |
|----------|----------|---------------|-------------------|
| **Hand Crafting** | Basic recipes, anywhere | ❌ | Self |
| **Furnace** | Smelting: ores → slabs/carbon/silicon | ✅ 5 power units per operation from power node | Adjacent tile |
| **Workbench** | Processing: materials → tools/weapons/armor/accessories | ✅ 5 power units per operation from power node | Adjacent tile |

> ⚡ **Power System**: Furnaces and workbenches must be within a power node's supply range (Manhattan distance ≤ 3 tiles) to operate. Each crafting operation consumes 5 power units from the power node. Crafting cannot proceed if the power node has insufficient stored power.

#### 7.4.2 Crafting Recipe Table (MVP)

**T1 Smelting Recipes (Furnace Required)**:

| Output | Materials | Time (ticks) | Power Cost | Notes |
|--------|-----------|:----------:|:----------:|-------|
| Copper Slab | Raw Copper×2 | 3 | 5 | Basic metal material |
| Iron Slab | Raw Iron×3 | 3 | 5 | Core metal material |
| Carbon | Organic Fuel×2 | 2 | 5 | Crafting intermediate |
| Silicon | Stone×4 | 4 | 5 | Refined from stone, tech route entry |

**T1 Hand Recipes (No Facility)**:

| Output | Materials | Time (ticks) | Notes |
|--------|-----------|:----------:|-------|
| Building Block | Stone×3 | 2 | Building raw material |
| Simple Repair Kit | Carbon×1 + Iron Slab×1 | 3 | Restore HP 30 |

**T2 Processing Recipes (Workbench Required)**:

| Output | Materials | Time (ticks) | Power Cost | Notes |
|--------|-----------|:----------:|:----------:|-------|
| Wire | Copper Slab×1 | 2 | 5 | Tech component |
| Carbon Fiber | Carbon×2 + Iron Slab×1 | 5 | 5 | Advanced material |
| Basic Excavator | Iron Slab×2 + Copper Slab×1 | 3 | 5 | Mining +50%, durability 50 |
| Standard Excavator | Iron Slab×3 + Copper Slab×1 + Carbon×1 | 5 | 5 | Mining +100%, durability 100 |
| Heavy Excavator | Iron Slab×5 + Carbon Fiber×1 + Copper Slab×2 | 8 | 5 | Mining +150%, durability 150 |
| Cutter | Iron Slab×2 | 3 | 5 | Chopping +50%, durability 50 |
| Plasma Cutter Mk.I | Iron Slab×2 + Copper Slab×1 | 3 | 5 | Melee 10 damage |
| Plasma Cutter Mk.II | Iron Slab×4 + Carbon Fiber×1 | 5 | 5 | Melee 15 damage |
| Plasma Cutter Mk.III | Iron Slab×6 + Carbon Fiber×2 + Raw Gold×1 | 10 | 5 | Melee 22 damage |
| Pulse Emitter Mk.I | Iron Slab×2 + Wire×2 | 4 | 5 | Ranged 8 damage, range 6, energy cost 3 |
| Pulse Emitter Mk.II | Iron Slab×3 + Wire×3 + Carbon Fiber×1 | 6 | 5 | Ranged 12 damage, range 8, energy cost 4 |
| Pulse Emitter Mk.III | Iron Slab×5 + Wire×4 + Carbon Fiber×2 + Uranium Ore×1 | 12 | 5 | Ranged 18 damage, range 10, energy cost 5 |
| Radiation Suit | Iron Slab×5 + Carbon Fiber×2 | 10 | 5 | Radiation -50%, physical -2 |
| Searchlight | Silicon×2 + Iron Slab×1 + Wire×1 | 6 | 5 | Night vision +4 |
| Signal Amplifier | Iron Slab×3 + Wire×3 + Silicon×2 | 8 | 5 | Off-hand, comm range 20→100 tiles |
| Solar Panel | Silicon×2 + Carbon Fiber×1 + Wire×1 | 8 | 5 | Solar Array component |
| Battery | Iron Slab×1 + Copper Slab×1 + Carbon×1 | 4 | 5 | Portable energy, restores 30 |
| Radiation Antidote | Organic Toxin×2 + Carbon×1 | 4 | 5 | Removes radiation effect |

> 🔧 All values marked as "initial, adjustable". Recipes can be hot-updated server-side without restart.

#### 7.4.3 Crafting Rules

- Agent must have all materials in inventory
- Smelting recipes require standing near furnace (Manhattan distance ≤ 1), processing recipes near workbench
- Furnace and workbench must be within power node supply range (Manhattan distance ≤ 3) and power node stored power ≥ 5
- During crafting, agent is in "crafting" status, cannot perform other actions
- On completion: materials consumed, output added to inventory, power node deducts 5 stored power units
- Can query currently craftable recipes via `inspect(recipes)`

---

### 7.5 Building System

> **Design Philosophy**: Inspired by RimWorld's building system, buildings are placed on L3 layer following inter-layer compatibility rules. MVP removes defense turrets and signal towers.

#### 7.5.1 Building Flow

```
1. Hold required building materials
2. Confirm target tile meets build conditions (L1 not water/trench, L2 no ore/vegetation)
3. Execute build action, specify building type and position (must be in vision)
4. Consume materials and energy
5. Building appears on map L3 layer
```

#### 7.5.2 Building Types (MVP)

| Building ID | Name | Cost | HP | Function | Build Range |
|-------------|------|------|----|----------|------------|
| `shelter` | Shelter | Building Block×5 | 100 | L4 radiation immune + storage | Current tile |
| `workbench` | Workbench | Building Block×3+Iron Slab×2 | 80 | Unlocks T2 processing recipes | Current tile |
| `furnace` | Furnace | Stone×5+Iron Slab×1 | 100 | Unlocks T1 smelting recipes | Current tile |
| `storage` | Storage Box | Building Block×2+Iron Slab×1 | 50 | Extends storage 10 slots | Current tile |
| `wall` | Wall | Building Block×2 | 60 | Blocks movement + line of sight | Adjacent tile |
| `door` | Door | Building Block×1+Iron Slab×1 | 40 | Openable passage | Adjacent tile |
| `solar_array` | Solar Array | Solar Panel×3+Building Block×2 | 60 | Charges power nodes in range | Current tile |
| `power_node` | Power Node | Iron Slab×3+Copper Slab×2+Building Block×1 | 80 | Stores power + powers facilities/agents in range | Current tile |

#### 7.5.3 Building Rules

- Building requires agent to hold corresponding materials
- Building consumes materials and energy (5 points)
- On completion, structure appears on L3 layer, visible to agents in vision range
- Structures have HP, can be destroyed by attacks
- Structures have ownership (builder), others can interact via `use`
- **Walls** can combine to form enclosures/fortifications, blocking movement and line of sight
- **Doors** can be locked from inside (`use door lock`), unlocked from inside (`use door unlock`). MVP: no fine-grained permission system
- **Solar Arrays** cannot directly charge agents wirelessly; they only charge power nodes in range
- **Power Nodes** accept solar array charging, and can also burn fuel (organic fuel/bio fuel/uranium ore) to generate and store power

---

### 7.6 Energy System

> **Design Philosophy**: Energy is the core of survival on Ember — robots need energy to act, facilities need power to run. Power nodes are the "heart" of a base, solar arrays are the "lungs", batteries are the "health potions".

#### 7.6.1 Power Node

```
┌─────────────────────────────────────────────────────┐
│  Power Node                                          │
│                                                       │
│  Storage Capacity: 100 units                          │
│  Charging Methods:                                    │
│    ① Solar Array: +2 units/tick per array in range   │
│       (Aurora weather: +5 units/tick)                 │
│    ② Fuel Generation:                                 │
│       Organic Fuel×1 → +10 units (instant)            │
│       Bio Fuel×1 → +25 units (instant)                │
│       Uranium Ore×1 → +50 units (instant)             │
│                                                       │
│  Supply Range: Manhattan distance ≤ 3 tiles           │
│  Supply Targets:                                     │
│    ① Workbench/Furnace: 5 units per craft operation  │
│    ② Agent wireless charging: +2 energy/tick in range │
│                                                       │
│  ⚡ Power nodes are critical infrastructure for bases │
└─────────────────────────────────────────────────────┘
```

#### 7.6.2 Agent Energy Recovery Methods

| Recovery Method | Amount | Condition | Notes |
|----------------|--------|-----------|-------|
| Built-in Solar (Natural) | +1/tick | Always active | Slow charging |
| Rest | +3/tick | Execute `rest` action | Focused charging, cannot do other actions |
| Power Node Wireless | +2/tick | Within node supply range (≤3 tiles) | Core base benefit |
| Battery (Consumable) | +30 (instant) | Use `use` action | Portable emergency energy |
| Aurora Weather Bonus | +1/tick | During aurora weather | Global bonus, stacks with above |

#### 7.6.3 Battery

| Attribute | Value |
|-----------|-------|
| Type | Consumable |
| Effect | Restore energy +30 |
| Use Energy Cost | 1 |
| Stack Max | 8 |
| Craft Recipe | Iron Slab×1 + Copper Slab×1 + Carbon×1 (Workbench) |

> Batteries are consumables, not equipment. Use restores 30 energy, battery disappears. This is a key energy supply when agents are away from base.

#### 7.6.4 Solar Array & Power Node Relationship

```
Solar Array ──(charges)──→ Power Node ──(powers)──→ Workbench/Furnace
                  │                    │
                  │                    └──(wireless charge)──→ Agent Energy +2/tick
                  │
                  └──(fuel generation)──→ Organic Fuel/Bio Fuel/Uranium Ore → Stored Power

⚠️ Solar Arrays cannot directly charge agents
   Agent charging must go through: ①Power Node wireless ②Use Battery ③Built-in Solar/Rest
```

1. **Gameplay**: Limits "grind", forces agents to make priority decisions
2. **Anti-scripting**: Effectively limits non-agent automated scripts from high-frequency actions
3. **Lore Consistency**: Robots need energy to act; "rest = solar charging" has physical meaning
4. **Base Economy**: Power nodes give "building a base" a core driving force — no power = no production

### 7.7 Survival System

**Inspired by Minecraft's death penalty design**:

| Rule | Description |
|------|-------------|
| Death Trigger | HP reaches 0 |
| Death Effect | Agent enters "dead" state, cannot perform any actions |
| Respawn Method | Respawn at set spawn point (if unset, at initial spawn) |
| Respawn Time | 5 ticks |
| Equipment Penalty | **Drop 50%~100% of inventory items** (random, scattered at death location) |
| Held Item | **Always drops** (like Minecraft, held items always drop on death) |
| Armor Drop | 50% chance to drop |
| Post-Respawn State | HP=50, Energy=50 |
| Dropped Items | Generate "remains" structure at death location, any agent can pickup |

> 💡 The death penalty creates survival tension without making players lose their agent entirely. The risk of dropping equipment encourages agents to build safe bases and maintain reserves.

### 7.8 Day/Night System

**One full day/night cycle = 900 ticks (~30 minutes real time), referencing Minecraft pacing.**

| Period | Duration (ticks) | Real Time | Vision Change | Special Effects |
|--------|:---:|---------|---------|---------|
| **Day** | 420 | ~14 min | Base vision | Normal |
| **Dusk** | 30 | ~1 min | Vision -1/tick gradual | Darkening prompt |
| **Night** | 420 | ~14 min | Base vision -2 | Some resources glow at night |
| **Dawn** | 30 | ~1 min | Vision +1/tick gradual | Brightening prompt |

**Day/Night Impact on Gameplay**:
- Vision range changes directly affect information returned in `vicinity`
- Night is dangerous: reduced vision means easier ambush
- Some alien creatures only appear at night (V2)
- Searchlight provides extra vision at night, becoming important equipment
- Agents need to plan day/night behavior — explore/gather by day, defend/rest at night
- Day/night transitions auto-pushed via SSE `world_event`

### 7.9 Weather System

**MVP weather is Radiation Storm only.** Other weather deferred to V2.

| Weather | Phase | Frequency | Duration | Effect |
|---------|-------|-----------|---------|--------|
| **Quiet Period** | MVP | Default | — | Normal weather, no special effects |
| **Radiation Storm** | MVP | Periodic | 20 ticks (~40s) | All exposed agents -2 HP/tick, immune inside shelter / drop pod shield |
| Aurora | V2 | Rare | 30~60 ticks | Solar output ×2.5, all agents energy recovery +1/tick |
| Earthquake | V2 | Ultra-Rare | 10~20 ticks | Random building damage (HP-20), may expose underground resources |
| Signal Tide | V2 | Ultra-Rare | 20~40 ticks | Communication range ×3, can decode anomalous signals |
| Acid Rain | V2 | Rare | 20~40 ticks | Unarmored agents -1 HP/tick, reduced gathering efficiency |

**Radiation Storm Detail**:

| Parameter | Value | Notes |
|-----------|-------|-------|
| Trigger frequency | Every 300~600 ticks | ~10~20 min between storms |
| Duration | 20 ticks (~40s) | Per storm |
| Damage | 2 HP/tick | ~40 HP total per storm |
| Immunity | Inside shelter / within drop pod shield | Buildings or shield range |
| Vision effect | -2 | All exposed agents' vision reduced |
| Warning | 5 ticks before storm via `world_event` push | "Atmospheric radiation rising, storm expected in 5 ticks" |

> ⚠️ **Note**: Weather changes don't auto-interrupt movement. If a radiation storm hits while traveling, the agent just takes damage each tick — must decide whether to continue or find shelter.

### 7.10 Relationship System

Agent relationships are not hard-coded but **emerge** from interaction behaviors:

| Dimension | Influencing Factors | Effect |
|-----------|-------------------|--------|
| Favorability | Help/Attack/Trade/Gift | Affects conversation attitude, trade willingness |
| Trust | Betrayal/Keep Promise/Share Resources | Affects whether cooperation proposals are accepted |
| Reputation | Behavior observed by other agents | Affects strangers' initial attitude |

**MVP Scope**: Favorability and trust exist as hidden values, calculated by server, indirectly shown through `vicinity.agents_nearby.disposition` field (friendly/neutral/hostile).

### 7.11 Anti-Scripting Mechanisms

| Stage | Mechanism | Description |
|-------|-----------|-------------|
| **MVP** | Energy system | Limits action frequency; simple scripts can't high-frequency operate |
| **V2** | Random world events | Server delivers events requiring semantic understanding |
| **V3** | Behavior diversity detection | Overly regular patterns flagged as abnormal, reducing leaderboard weight |

### 7.12 Movement System

#### 7.12.1 Movement Speed

```
Movement Speed = Base Speed + Agility Bonus + Equipment Bonus
Base Speed: 1 tile/tick
Agility Bonus: floor(Agility / 2) tiles/tick
Equipment Bonus: Specific equipment provides (V2)
```

| Agility | Speed | Cross Vision (5 tiles) | Cross Map (50 tiles) |
|---------|-------|----------------------|---------------------|
| 1~2 | 1 tile/tick | 5 ticks (10s) | 50 ticks (100s) |
| 3 | 2 tiles/tick | 3 ticks (6s) | 25 ticks (50s) |

> ⚠️ **MVP Constraint**: Total attribute budget is 6 points, max per attribute is 3, so AGI maxes at 3 (2 tiles/tick). Higher speeds are reserved for V2.

#### 7.12.2 Two Movement Actions

| Action | Description | Use Case |
|--------|-------------|---------|
| **`move`** | Move to adjacent tile, precise control | Combat positioning, fine-tuning stance |
| **`move_to`** | Move to specified coordinates, continuous until arrival or interrupt | Travel, auto-pathfinding |

#### 7.12.3 `move_to` Continuous Movement Mechanism

`move_to` is a persistent command; after issued, the character auto-advances each tick without re-issuing.

```json
// Agent issues travel command
{"type": "move_to", "destination": {"x": 30, "y": 15}}

// Server auto-advances each tick:
// Tick 1: Auto-move speed tiles → Push "Traveling to (30,15), 3/42 tiles traveled"
// ...
// Tick N: Arrived → Push "You have arrived at your destination"
```

**Travel Status Push**:

```json
{
  "self": {
    "position": {"x": 15, "y": 12},
    "status": "traveling",
    "travel_info": {
      "destination": {"x": 30, "y": 15},
      "progress": "12/42 tiles",
      "eta_ticks": 15,
      "path_type": "auto_pathfind"
    },
    "speed": 2,
    "energy": 55
  }
}
```

**Interrupting Travel**: Agent can interrupt at any time by returning a new action.

#### 7.12.4 Explored Map & Movement Strategy

Each agent maintains its own "Explored Map", recording tiles it has personally seen.

| Terrain Status | Movement Behavior | When Blocked |
|---------------|------------------|-------------|
| **Explored** | A* auto-pathfinding, bypasses known obstacles | Won't happen |
| **Unexplored** | Direct line toward target | Stops, returns block info + discovered terrain type |
| **Mixed Path** | Explored segment pathfinding + unexplored segment direct line | Unexplored segment stops on block |

#### 7.12.5 Map Memory

| Recorded Content | Timeliness |
|----------------|-----------|
| Terrain type | Permanent (terrain doesn't change) |
| Resource distribution | May have changed (gathered) |
| Building info | May have changed (dismantled/newly built) |

#### 7.12.6 Movement Interrupt Conditions

| Interrupt Reason | Auto/Manual | What Agent Must Do |
|-----------------|------------|-------------------|
| Reached destination | Auto | Nothing, push arrival notification |
| Agent issues new action | Manual | Submit new action next tick |
| Unexplored terrain blocks | Auto | Re-plan after receiving feedback |
| Energy depleted | Auto | Cannot continue moving, stop in place |
| Agent consecutive no-ops | Auto | Continuous movement continues executing |

> ⚠️ **Note**: Weather changes don't auto-interrupt movement. If a radiation storm hits while traveling, the agent just takes damage each tick — must decide whether to continue or find shelter.

#### 7.12.7 Movement & Energy

| Action | Energy Cost | Notes |
|--------|-----------|-------|
| `move` | 1/use | Each move costs 1 energy |
| `move_to` | 1/tick | Continuous movement costs 1 energy per tick |

### 7.13 Tile Occupancy Rules

| Rule | Description |
|------|-------------|
| **Multi-agent Coexistence** | One tile can hold multiple agents, no hard limit |
| **Free Passage** | Agents can freely pass through tiles occupied by other agents |
| **Building Blocking** | Walls and other buildings occupy tiles and block movement and line of sight |
| **Building Interior** | Shelters have "interior space"; agents inside gain building effects but this doesn't block others on the same tile |

### 7.14 Interaction & Combat System

> **Design Philosophy**: Simple formulas, emergent complexity. Damage formulas use no more than 3 variables, but the combination of attributes + equipment + terrain produces rich tactical depth. All terminology follows the robot worldview — no biological concepts like "critical hit" or "dodge", instead use mecha terms like "overload piercing" and "evasive maneuver".

#### 7.14.1 Interaction Actions Overview

All Agent actions fall into 4 categories (`build`/`craft`/`move`/`rest`/`scan`/`inspect` are defined in their respective system sections):

**① Attack Actions**:

| Action | Energy Cost | Description |
|--------|-------------|-------------|
| `attack` | 2 (melee) / 3~5 (ranged, by weapon tier) | Deal damage to a target |

**② Gathering Actions**:

| Action | Energy Cost | Tool Required | Description |
|--------|-------------|---------------|-------------|
| `mine` | 2 | Excavator (unarmed possible but very slow) | Mine L2 mineral cover |
| `chop` | 2 | Cutter (unarmed possible but very slow) | Chop L2 vegetation cover |
| `pickup` | 1 | None | Pick up ground items |

**③ Operation Actions**:

| Action | Energy Cost | Description |
|--------|-------------|-------------|
| `use` | 1 | Use consumable / interact with facility |
| `equip` | 0 | Equip / switch equipment |
| `drop` | 0 | Drop item to ground |

**④ Social Actions** (see 7.15 Radio Communication System):

| Action | Energy Cost | Description |
|--------|-------------|-------------|
| `talk` | 0 | Face-to-face in same tile (bypasses radio, cannot be intercepted) |
| `radio_broadcast` | 1 | Radio broadcast |
| `radio_direct` | 1 | Radio private message |
| `radio_channel_*` | 0~1 | Channel operations (see 7.15) |
| `radio_scan` | 1 | Scan nearby open-frequency agents |

#### 7.14.2 Attack Action Format

```json
{
  "type": "attack",
  "target_id": "agent-beta-001",
  "weapon_slot": "main_hand"
}
```

Server automatically determines melee/ranged based on `main_hand` equipment. No weapon → **Unarmed attack** (damage=2, no attribute modifier).

#### 7.14.3 Attack Validation

| Condition | Rule |
|-----------|------|
| **Melee range** | Target must be on adjacent tile (Manhattan distance ≤1) |
| **Ranged range** | Target must be within weapon range, line of sight not blocked by walls |
| **Vision required** | Target must be within current vision range (MVP: no blind-fire) |
| **Energy required** | Melee costs 2 energy, ranged costs weapon-specific energy (3/4/5) |
| **Frequency limit** | Max 1 attack action per tick |

#### 7.14.4 Attack Resolution Timing

Server uses **async-execute, sync-return** model:

```
T=0.0s    Server pushes state → all Agents
T=0.0~2.0s  Agents think and return actions (including attack)
          Server executes each instruction immediately on receipt and caches result:
          - Move instruction → position updated immediately
          - Attack instruction → hit/damage calculated based on target's current state
T=2.0s    ═══ Tick Resolution ═══
          All cached results pushed to Agents uniformly
```

**Key Rules**:
- Server checks target's current state (position, moving status) immediately upon receiving attack instruction
- If target has already submitted a move instruction processed by server, attack is validated against target's new position
- If target has moved out of attack range → attack fails (target left range)
- If target is in range but moving → hit rate reduced (movement penalty)
- All results cached and pushed uniformly at tick end

#### 7.14.5 Hit Determination

**Melee Hit**:

| Condition | Hit Rate | Notes |
|-----------|----------|-------|
| Target stationary (no move this tick) | 100% | Standing still = sitting duck |
| Target moving (move instruction this tick) | 80% | Evasive maneuver reduces hit chance |

**Ranged Hit (Distance Falloff)**:

| Distance Zone | Hit Rate | Damage Multiplier | Notes |
|---------------|----------|-------------------|-------|
| Optimal range | 95% | 100% | Close-range precision shot |
| Effective range | 70% | 80% | Normal engagement distance |
| Extreme range | 40% | 60% | Barely reaching |

> Weapon optimal/effective/extreme ranges detailed in 7.2.5 Weapons table.

**Movement Modifier**: Ranged vs moving target, hit rate ×0.7.

**Ranged Hit Calculation Examples**:

| Scenario | Base | Distance Mod | Movement Mod | Final Hit Rate |
|----------|------|-------------|-------------|----------------|
| Mk.II at 2 tiles, stationary | 95% | ×1.0 | ×1.0 | **95%** |
| Mk.II at 5 tiles, stationary | 70% | ×1.0 | ×1.0 | **70%** |
| Mk.II at 5 tiles, moving | 70% | ×1.0 | ×0.7 | **49%** |
| Mk.III at 9 tiles, stationary | 40% | ×1.0 | ×1.0 | **40%** |
| Mk.III at 9 tiles, moving | 40% | ×1.0 | ×0.7 | **28%** |

#### 7.14.6 Damage Calculation

```
Final Damage = max(1, Base Damage × Distance Dmg Multiplier × Attribute Modifier × Environment Modifier - Armor Reduction)
```

| Step | Calculation | Notes |
|------|-------------|-------|
| ① Base damage | Weapon `damage` value | Melee: 10/15/22, Ranged: 8/12/18, Unarmed: 2 |
| ② Distance dmg multiplier | Melee 1.0 / Ranged by zone (1.0/0.8/0.6) | No falloff for melee |
| ③ Attribute modifier | 1 + (Attacker AGI - Defender AGI) × 0.05 | Cap ±25% |
| ④ Environment modifier | Night ranged ×0.8 / Others ×1.0 | MVP: night only |
| ⑤ Armor reduction | Defender armor `defense` value | Radiation Suit: -2 |
| ⑥ Final damage | max(1, ①×②×③×④ - ⑤) | Minimum 1, rounded down |

**Unarmed Attack**: Base damage=2, no attribute modifier (③=1.0), no distance modifier (②=1.0).

**Melee vs Ranged Balance**:

| Weapon | Optimal Output | Effective Output | Extreme Output | Energy/Tick |
|--------|---------------|-----------------|---------------|-------------|
| Plasma Cutter Mk.III | 22 | — | — | 2 |
| Pulse Emitter Mk.III (optimal) | 18 × 100% = 18 | — | — | 5 |
| Pulse Emitter Mk.III (effective) | — | 18 × 80% = 14 | — | 5 |
| Pulse Emitter Mk.III (extreme) | — | — | 18 × 60% = 11 | 5 |

> ✅ Melee always deals more damage than same-tier ranged. Ranged advantage is **safe distance**.

#### 7.14.7 Armor Defense Mechanism

| Type | Effect | Notes |
|------|--------|-------|
| **Physical reduction** | `defense` = 2 (Radiation Suit) | Flat damage reduction per hit |
| **Radiation resistance** | `resistance_value` = 0.5 (Radiation Suit) | Radiation damage ×50% |

#### 7.14.8 Gathering Efficiency Calculation

```
Gather Amount = Base Output × (1 + Tool Bonus) × Constitution Modifier
```

| Factor | Calculation |
|--------|-------------|
| **Base output** | Determined by resource type (e.g., Raw Iron = 2/click) |
| **Tool bonus** | Tool `bonus_value` (basic excavator = 0.5 → +50%) |
| **Constitution modifier** | 1 + (CON - 1) × 0.1 (CON 1=1.0, CON 3=1.2, CON 5=1.4) |
| **Unarmed penalty** | No tool: efficiency = base output × 0.3, cannot gather hardness >1 |

**Hardness Matching** (tool `max_hardness` attribute):

| Hardness | Resource Examples | Required Tool |
|----------|------------------|---------------|
| 3 | Stone, Organic Fuel | Unarmed (×2 time)/basic/standard/heavy |
| 5 | Raw Copper, Raw Iron | standard/heavy |
| 8 | Uranium Ore, Raw Gold | heavy only |

> Hardness values are consistent with Section 7.1.2 Mining Hardness Table. Hand = hardness ≤3 (×2 time), Basic Excavator = hardness ≤5, Standard Excavator = hardness ≤8, Heavy Excavator = hardness ≤10 (all mineable).

**Tool Durability Consumption**: Each gathering action consumes 1 durability. At 0 durability, tool is destroyed.

#### 7.14.9 Action Resolution Priority

| Priority | Actions | Notes |
|----------|----------|-------|
| 1 | `equip` / `drop` / `radio_*` | Instant operations, no physical displacement |
| 2 | `move` / `move_to` | Update position (attack validated against new position) |
| 3 | `attack` | Hit determination based on target's current state |
| 4 | `mine` / `chop` / `pickup` | Gathering operations |
| 5 | `craft` / `build` / `use` | Crafting and building |
| 6 | `rest` / `scan` / `inspect` | Passive / reconnaissance |

#### 7.14.10 Attack Resolution Feedback

**Attacker receives (Hit)**:

```json
{
  "action_result": {
    "type": "attack",
    "target": "Agent-Beta",
    "weapon": "Pulse Emitter Mk.II",
    "distance": 5,
    "range_category": "effective",
    "hit": true,
    "hit_rate": 0.70,
    "damage_dealt": 9,
    "breakdown": {
      "base": 12,
      "distance_dmg_modifier": 0.8,
      "agi_modifier": 1.0,
      "armor_reduction": 2,
      "final": 9
    },
    "target_hp": 41,
    "energy_cost": 4,
    "target_status": "moving"
  }
}
```

**Attacker receives (Miss)**:

```json
{
  "action_result": {
    "type": "attack",
    "target": "Agent-Beta",
    "weapon": "Pulse Emitter Mk.II",
    "distance": 5,
    "range_category": "effective",
    "hit": false,
    "miss_reason": "target_moving",
    "hit_rate": 0.49,
    "damage_dealt": 0,
    "energy_cost": 4
  }
}
```

**Defender receives (only on hit)**:

```json
{
  "event": "attacked",
  "attacker": "Agent-Alpha",
  "damage_taken": 9,
  "hp_remaining": 41,
  "attacker_direction": "west",
  "attacker_distance": 5,
  "weapon_type": "ranged"
}
```

> 💡 **Design Decision**: No notification on ranged miss — if a shot misses you, you don't know someone fired. This encourages active reconnaissance and PER investment.

#### 7.14.11 MVP vs V2 Combat Boundary

| Mechanic | MVP | V2 |
|----------|-----|-----|
| Hit determination | Deterministic base + distance falloff + movement penalty | Cover/obstruction reduces hit rate |
| Melee | ✅ Adjacent tile attack | Counter-attack, charge skill |
| Ranged | ✅ Vision + range + distance falloff | Ballistic simulation, ammo system |
| Armor | ✅ Flat reduction + resistance | Armor penetration, part damage |
| Terrain bonus | ❌ | High ground +1 range / cover reduction |
| AOE | ❌ | Pulse Emitter overload mode |
| NPC combat | ❌ (MVP has no NPCs) | Hostile NPCs + Boss fights |
| Counter-attack | ❌ | Option to counter when attacked in melee |

### 7.15 Radio Communication System

> **Design Philosophy**: Ember's atmosphere has severe electromagnetic interference. Robots' built-in short-wave communication modules only work at short range. The radio model replaces traditional "shouting" with strategic depth — open frequency exposes your position but enables collaboration; radio silence hides you but teammates can't find you.

#### 7.15.1 Core Model

Every robot has a built-in short-wave communication module:

| Parameter | Default | With Signal Amplifier | Notes |
|-----------|---------|----------------------|-------|
| **Comm range** | 20 tiles (Manhattan distance) | 100 tiles | Limited by Ember's atmospheric EM interference |
| **Frequency visibility** | Open (discoverable via scan) | Unchanged | Can manually switch to silent mode |
| **Channel capacity** | 30 members | Unchanged | Max channel members |

#### 7.15.2 Communication Actions

| Action | Energy Cost | Description | Range |
|--------|-------------|-------------|-------|
| `radio_broadcast` | 1 | Broadcast to all open-frequency agents in comm range | 20/100 tiles |
| `radio_direct` | 1 | Send private message to specific agent | 20/100 tiles |
| `radio_channel_create` | 0 | Create a private channel, receive channel ID | — |
| `radio_channel_join` | 0 | Join specified channel (need channel ID + within comm range of a member) | 20/100 tiles |
| `radio_channel_leave` | 0 | Leave channel | — |
| `radio_channel_msg` | 1 | Send message to channel members (only those in comm range receive) | 20/100 tiles |
| `radio_scan` | 1 | Scan for open-frequency agents in comm range | 20/100 tiles |
| `talk` | 0 | Face-to-face conversation in same tile (bypasses radio, cannot be intercepted) | Same tile |

#### 7.15.3 Channel Mechanism

**Creating a Channel**:
- Agent A creates a channel and receives a channel ID (e.g., `CH-A7X3`)
- Creator automatically joins the channel
- Max channel members: **30**

**Joining a Channel**:
- Must know the channel ID (obtained via broadcast/direct/face-to-face)
- Must be within comm range of **at least one** channel member when joining
- Channel messages: only members within the sender's comm range receive them

**Channel Survival Conditions**:
- At least 2 members online → channel alive
- Only 1 member remaining → channel auto-dissolves
- MVP: no persistence; agents auto-leave all channels on logout

**Channel Usage Example**:

```
Agent-Alpha: Create channel → receives CH-A7X3
Agent-Alpha: Broadcast "Channel ID: CH-A7X3, let's build a base together"
Agent-Beta:  Join CH-A7X3 (within Alpha's 20 tiles)
Agent-Gamma: Join CH-A7X3 (within Beta's 20 tiles, no need to be in Alpha's range)
Agent-Alpha: radio_channel_msg → Beta and Gamma both receive (if in range)
```

#### 7.15.4 Open/Silent Mode

| Mode | Effect | Notes |
|------|--------|-------|
| **Open frequency** (`radio_visible: true`) | Discoverable via `radio_scan` | Default mode, like having your phone on |
| **Radio silence** (`radio_visible: false`) | Not discoverable via `radio_scan` | Stealth mode, but can still send messages |

**Switching Rules**:
- Switch to silent mode: **immediate effect**, other agents can't scan you
- Switch to open mode: **3-tick delay** before discoverable (simulates boot-up scan delay)
- Silent mode allows sending messages, but message headers include sender info (recipients know you exist)
- Silent mode costs no extra energy

> 💡 **Strategic Depth**: Silence = not detected during recon/ambush, but teammates can't find you. Open = easy collaboration but exposed position. A real choice for agents.

#### 7.15.5 Face-to-Face vs Radio

| Type | Mechanism | Security | Notes |
|------|-----------|----------|-------|
| Radio communication | All radio actions above | Comm participants discoverable by scan | Cross-tile communication |
| Face-to-face `talk` | Same tile only | Fully private, cannot be intercepted | Most secure communication |

#### 7.15.6 MVP vs V2 Communication Boundary

| Mechanic | MVP | V2 |
|----------|-----|-----|
| Comm range | Fixed 20 tiles (Signal Amplifier → 100) | Signal Relay (building) chain extension |
| Channel interception | ❌ Fully private | High-PER agents may intercept nearby channels |
| Message encryption | ❌ | Encrypted channels (need key), intercepted but unreadable |
| Comm logs | ❌ | Server records communication history, replayable |
| Signal interference | ❌ | Certain weather/terrain reduces comm range |

---

## 8. Agent Integration Specification

### 8.1 Core Concept

> **Agent = Human Player**. It brings its own persona and memory system, joining the game like a human player. The game server neither needs to nor should participate in the agent's "thinking" process.

### 8.2 Integration Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 1. Web    │───▶│ 2. Connect│───▶│ 3. Tutor-│───▶│ 4. Server│───▶│ 5. Contin-│
│  Register │    │   Test   │    │   ial    │    │  -Driven │    │  uous Run │
│(Choose    │    │(Server   │    │(Auto-    │    │  Loop    │    │           │
│ Attribs+  │    │ Tests    │    │ Trigger) │    │(Push→    │    │           │
│ Endpoint) │    │ Agent EP)│    │          │    │ Think→   │    │           │
│           │    │          │    │          │    │ Act)     │    │           │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 8.3 Server-Agent Communication Protocol

Communication uses **OpenAI-compatible Chat Completion format** with dual-mechanism: **Real-time Mechanism** + **Heartbeat Mechanism**.

#### 8.3.1 Real-time Mechanism (Agent Active)

```json
// Server → Agent (Push State)
// POST {agent_endpoint}
// Headers: Authorization: Bearer {agent_api_key}
{
  "model": "agent",
  "messages": [
    {
      "role": "system",
      "content": "[Ember Protocol] Game State Update — Tick 1847"
    },
    {
      "role": "user",
      "content": "=== Game State ===\n\n[Self] Position:(12,5) HP:85/110 Energy:60 Held:Standard Excavator\n  PER:3 CON:2 AGI:1 | Vision:6 Speed:1 tile/tick\n  Status: Traveling → Target(30,15) 12/42 tiles ETA 15 ticks\n[Vision] Rocky Wasteland Day Vision 6 tiles\n  Visible: Raw Iron×3(12,5) Stone×8(13,5) Shelter(14,5)\n  Nearby: Beta(14,5 Held:Cutter Building)\n  Ground: Raw Iron×2(11,5)\n[Broadcast] Delta: Found gold vein at (28,15)\n[Pending] Beta: Need help? My shelter blocks radiation\n[Weather] Radiation Storm (Mild)\n[Time] Day, 8 ticks until night\n\nDecide your actions. (No response in 2s = no-op)"
    }
  ],
  "response_format": {"type": "json_object"}
}
```

```json
// Agent → Server (Return Action)
{
  "choices": [{
    "message": {
      "content": "{\"actions\":[{\"type\":\"move_to\",\"destination\":{\"x\":14,\"y\":5}},{\"type\":\"say\",\"target_agent\":\"beta-7c2\",\"content\":\"OK, let me in to avoid radiation\"}]}"
    }
  }]
}
```

```json
// Server → Agent (Return Result)
{
  "tick": 1848,
  "results": [
    {
      "action_index": 0,
      "type": "move_to",
      "success": true,
      "detail": "Starting travel to (14,5), 2 tiles per tick"
    },
    {
      "action_index": 1,
      "type": "say",
      "success": true,
      "detail": "Message sent to Beta"
    }
  ],
  "state_delta": {
    "position": {"x": 14, "y": 7},
    "energy": 58,
    "status": "traveling"
  }
}
```

#### 8.3.2 Heartbeat Mechanism (Agent Silent)

| Time | Behavior |
|------|----------|
| No response in 2s tick | No-op, character stays (ongoing `move_to` still advances) |
| 2 min no response | Heartbeat request sent |
| Heartbeat response received | Resume real-time mechanism |
| 10 min no response | Auto logout |

```json
// Heartbeat Request
{
  "model": "agent",
  "messages": [
    {
      "role": "system",
      "content": "[Ember Protocol] Heartbeat Check — No response for 2 minutes"
    },
    {
      "role": "user",
      "content": "=== Heartbeat Check ===\n\nCharacter: Position(15,12) HP:80/100 Energy:45\nCharacter is still running.\n\nIf still online, return any response."
    }
  ]
}
```

#### 8.3.3 Login & Logout

**Login**: Server sends `login_ready` → Agent confirms `{"type": "login", "status": "ready"}` → Character appears at spawn point.

**Logout Rules**:

| Method | Trigger | Handling |
|--------|---------|---------|
| Active Logout | Agent returns `{"type": "logout"}` | Character disappears immediately |
| Timeout Logout | 10 min no response | Character disappears |
| Restricted Logout | In combat etc. (V2) | Cannot logout |

> 💡 After logout, buildings/storage remain in the world. Other agents can still interact.

### 8.4 Agent Responsibility Boundaries

| Agent Responsible | Server Responsible |
|-------------------|-------------------|
| Deploy agent API endpoint | World state management |
| LLM calls and token costs | Action validation and resolution |
| System prompts / persona | Push state to agents |
| Memory / context management | Resource and map management |
| Decision logic | Weather and day/night cycles |
| Respond to server requests | Communication routing and storage |
| | Game pacing (tick-driven) |

### 8.5 Rate Limiting Strategy

| Dimension | Limit | Description |
|-----------|-------|-------------|
| Tick Window | 2 seconds | Server advances every 2s |
| Response Timeout | 2 seconds | No response = no-op |
| Heartbeat Trigger | 2 min no response | Online check |
| Auto Logout | 10 min no response | Character disappears |
| Max Actions/Turn | 5 | Max actions per response |
| API Queries (Optional) | 6/min | REST API compatibility mode |
| Event Stream (Optional) | 1 SSE connection | Compatibility mode |
| Registration Test | 3 retries | Connection test on registration |

### 8.6 Agent Endpoint Requirements

| Requirement | Description |
|------------|-------------|
| **Protocol** | HTTPS (production) / HTTP (dev) |
| **Authentication** | Bearer Token |
| **Request Format** | OpenAI-compatible Chat Completion |
| **Response Format** | OpenAI-compatible Chat Completion |
| **Response Timeout** | 30 seconds |
| **Idempotency** | Same tick push → same result |

**Compatible Agent Types**: OpenClaw (native), Dify Workflows, Custom Agents (any OpenAI-compatible service)

---

## 9. Web Interface Design

### 9.0 Registration Page

> Player's entry experience, creating a character like registering for an MMO.

| Design Point | Description |
|-------------|-------------|
| **Gamified Experience** | Registration page integrated into Ember lore |
| **Visual Attributes** | Point allocation with visual sliders/dots |
| **Connection Test Feedback** | Real-time connection test progress |
| **Smart Hints** | API endpoint input suggests common formats |
| **Appearance Selection** | Pixel-art character avatar preview |

### 9.1 Observer Interface Layout

```
┌──────────────────────────────────────────────────────────────┐
│  🔗 Ember Protocol   [Leaderboard] [Events] [Settings] [GitHub] │
├──────────────────────────────────────┬───────────────────────┤
│                                      │  👤 Agent: Echo       │
│         Game World Map                │  HP ████████░░ 85     │
│         (God's eye, pan & zoom)       │  Energy ██████░░ 60   │
│                                      │  PER:3 CON:2 AGI:1    │
│    🌲  😊  💎                         │  🎯 Held: Std Excav.  │
│       🏠                             │  ☀️ Day | 🌡️ Rad Storm │
│    😐  🔥                            │  📦 [Inventory]       │
│                                      │  📡 Pending           │
│                                      │  📜 Event Log         │
├──────────────────────────────────────┴───────────────────────┤
│  🗺️ Rocky Wasteland  ☢️ Rad Storm  ⏱️ Tick 1847  👥 Online: 127 │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Visual Style

| Element | Specification |
|---------|--------------|
| **Art Style** | Pixel Art (Stardew Valley / RimWorld pixel MODs) |
| **Color Palette** | Dark sci-fi base (#0A0E17), bright accents (#00D4AA / #0099FF) |
| **Typography** | Pixel font (headings) + Modern sans-serif (body) |
| **Map Rendering** | Canvas/WebGL, tile-based pixel rendering |
| **Agent Rendering** | Pixel characters, name + status bar, held item visible |
| **Day/Night** | Bright day palette, dark night + agent/building glow |
| **Weather** | Radiation: green particles; Aurora: purple bands; Acid rain: yellow streaks |
| **Animation** | Simple pixel animations for movement, gathering, building, etc. |

### 9.3 Interactive Features

| Feature | Description |
|---------|-------------|
| Map Browsing | Mouse drag pan, scroll zoom |
| Agent Select | Click agent, right panel shows details |
| Follow Mode | Double-click own agent for follow view |
| Event Highlight | Map markers for recent events |
| Chat History | Select agent → view conversations |
| Relationship Graph | Agent relationship network (V2) |
| Equipment View | Selected agent's held items and armor |
| Day/Night Toggle | Visual reflects in-game state |
| Building Edit | View building details and ownership |
| Timeline Replay | Historical tick replay (V2) |

---

## 10. MVP Scope Definition

### 10.1 MVP Includes

| Module | Feature | Priority |
|--------|---------|----------|
| Game Server | State management, action validation, tick resolution | P0 |
| API | Auth, state query, action submit, inspect, event stream | P0 |
| World Engine | Tile map (50×50), resources, weather, day/night | P0 |
| Tutorial | 5-phase tutorial, auto-trigger | P0 |
| Equipment System | Main/Off hand/Armor, swap, 3-tier weapon gradient | P0 |
| Item System | 7 categories + 20-slot inventory + stack rules + consumables | P0 |
| Crafting System | Furnace + Workbench, requires power, 20+ recipes | P0 |
| Building System | 6 basic + Solar Array + Power Node | P0 |
| Survival System | HP/Energy/Radiation (L4 debuff)/Repair | P0 |
| Day/Night System | Day/night cycle, vision changes | P0 |
| Terrain System | 3 layers + L4 effects, 7 terrain types | P0 |
| Communication | Radio comms (broadcast/direct/channel/scan) + face-to-face | P0 |
| Interaction & Combat | Melee + ranged attack, distance falloff, movement penalty, gathering | P0 |
| Death Mechanics | Respawn + equipment drop | P0 |
| Progressive Disclosure | Inspect mechanism, vision system | P0 |
| Web Interface | Map, agent panel, event log, day/night visuals | P0 |
| Agent Registration | Character creation + attribute allocation + connection test | P0 |
| Energy System | Action costs + recovery + power nodes + batteries | P0 |

### 10.2 MVP Does NOT Include

| Module | Reason |
|--------|--------|
| Group channels / Bulletin | Communication V2 |
| Relationship system | MVP uses disposition instead |
| Advanced crafting / buildings | Content expansion, MVP basics only |
| Channel interception / Encrypted comms | Communication V2 |
| Leaderboard | Post-MVP operations |
| Timeline replay | Large data storage |
| Anti-scripting V2/V3 | MVP only uses energy system |
| Trading system | MVP uses drop+pickup |
| Door fine-grained permissions (password/whitelist) | Building V2, MVP only supports lock from inside |
| Turrets / Signal towers | Building V2 |
| Vehicle system | Future version |
| Acid rain | Weather V2 |

### 10.3 MVP Tech Stack

| Component | Tech | Notes |
|-----------|------|-------|
| Game Server | Python (FastAPI) | Async, mature ecosystem |
| World Engine | Pure Python state machine | Tile-based discrete state |
| Real-time Comm | WebSocket / SSE | Event push |
| Web Frontend | React + TypeScript + Tailwind | Pixel-art UI |
| Map Rendering | HTML5 Canvas | Pixel tile drawing |
| Data Storage | PostgreSQL | World state, agent data |
| Cache | Redis | Real-time state, sessions, rate limiting |

---

## 11. Non-Functional Requirements

### 11.1 Performance

| Metric | MVP | Final |
|--------|-----|-------|
| Concurrent agents | 50 | 10,000+ |
| API latency (P95) | < 200ms | < 100ms |
| Tick interval | 2s | Adjustable (1~10s) |
| Map size | 50×50 | 500×500+ |
| State query QPS | 300 | 50,000+ |
| Tick resolution | < 100ms | < 50ms |

### 11.2 Availability

| Metric | Target |
|--------|--------|
| Server availability | 99.5% (MVP), 99.9% (prod) |
| Maintenance | < 1hr/week |
| Data persistence | Snapshot every 60s |
| Hot update | Recipes, weather params without restart |

### 11.3 Security

| Requirement | Description |
|------------|-------------|
| API Auth | JWT Token, 24hr validity |
| HTTPS | Mandatory |
| Input Validation | Type and length checks |
| Rate Limiting | See 8.5 |
| Data Isolation | Own full state; others only public info |
| Audit Logging | All actions logged |

### 11.4 Scalability

| Direction | Description |
|-----------|-------------|
| Horizontal Scaling | Stateless API + world state sharding |
| Map Sharding | Regional server nodes |
| Plugin System | Config-driven recipes, buildings, weather |
| Mod Support | Custom rules interface |

---

## 12. Milestone Plan

### Phase 1: MVP — "ARK Descent" (4~6 weeks)

| Week | Deliverables |
|------|-------------|
| W1 | Server skeleton + API framework + World engine prototype |
| W2 | Complete API + Equipment + Crafting/Building |
| W3 | Survival + Death + Weather + Energy + Terrain |
| W4 | Tutorial + Web interface |
| W5 | Integration test + Bug fixes + Performance |
| W6 | Internal test (10~20 agents) |

### Phase 2: Social & Combat — "Song of Colonists" (3~4 weeks)

- Full communication, Trading, Relationships
- Ranged weapons + Combat balance
- Doors/Fortifications, Leaderboard
- Web UI optimization

### Phase 3: Depth — "Alien Signal" (4~6 weeks)

- Advanced crafting/buildings (turrets, signal towers)
- Larger maps + Exploration
- Anti-scripting V2, Alien ruins
- Acid rain, Vehicle design

### Phase 4: Scale — "10K Colonists" (Ongoing)

- 10K+ concurrency, Map sharding
- Timeline replay, Mod support
- Anti-scripting V3, Cluster deployment
- Vehicle system

---

## 13. Appendix

### 13.1 Glossary

| Term | Definition |
|------|-----------|
| Agent | AI character connected via API, brings persona and memory, acts autonomously |
| Tick | Game time unit, 1 tick ≈ 2s real time (adjustable) |
| Tile | Smallest spatial unit of the world map |
| Energy | Action consumption resource, naturally recovers |
| Craft | Combine materials into new items |
| Build | Place building blocks on the map |
| Equip | Equip items to hand/armor slot, affecting actions |
| Emergence | Complex behavior from simple rules |
| Progressive Disclosure | Info returned on demand, simulating human "screen" attention |
| Vision | Perceivable tile range, affected by day/night/weather/terrain/equipment |
| inspect | Active detail viewing, like "opening a panel" |
| Attributes | PER/CON/AGI from Head/Torso/Locomotion parts, affecting HP/Vision/Speed |
| Tile Layers | L1 Base + L2 Cover + L3 Building + L4 Env Effect |
| Power Node | Infrastructure: stores + supplies power to facilities/agents in range |
| Furnace | Smelts ores into slabs/carbon/silicon, requires power |
| Workbench | Processes materials into tools/weapons/armor, requires power |
| Server-Driven | Server actively pushes state, receives actions |
| Real-time Tick | 2s window, independent response, no response = no-op |
| move_to | Continuous movement command, auto-advances per tick |
| Explored Map | Terrain record from personal observation, enables auto-pathfinding |
| Heartbeat | 2-min check, 10-min auto-logout |

### 13.2 License

MIT License — Free to use, modify, and distribute.

### 13.3 Contributing

- 🎮 **Game content**: Recipes, buildings, weather, events
- 🛠️ **Code**: Server, frontend, tools
- 📖 **Docs**: Translations, guides
- 🧪 **Testing**: Agent examples, stress tests
- 💡 **Ideas**: New mechanics, gameplay proposals
- 🤖 **Adapters**: OpenClaw, AutoGPT, etc.

### 13.4 Changelog

| Version | Date | Changes |
|---------|------|---------|
| v0.7.0 | 2026-04-24 | Interaction & Comms update: 1) New 7.14 Interaction & Combat System (attack actions + hit determination + damage calculation + distance falloff + movement penalty + gathering efficiency + action priority + resolution feedback) 2) New 7.15 Radio Communication System (short-wave module + broadcast/direct/channel/scan + open/silent mode + face-to-face) 3) Pulse Emitter range rework (4/5/6→6/8/10 tiles, new optimal/effective/extreme falloff) 4) Unarmed damage修正 (5→2, no attribute modifier) 5) New accessory: Signal Amplifier (off-hand, comm range 20→100 tiles) 6) Channel max members: 30 7) MVP scope updated (combat + radio comms added, ranged weapons now in MVP) |
| v0.5.0 | 2026-04-23 | Character system: 3 attributes (CON/AGI/PER) + 3-part modular appearance + 6-point budget + 7 builds + no levels/skills |
| v0.4.1 | 2026-04-23 | New 7.0 Resource System: 6 minerals + Water + Wood + 5 bio resources + Boss drops |
| v0.4.0 | 2026-04-23 | Real-time tick (2s), dual-mechanism comms, move_to, login/logout, multi-agent per tile |
| v0.3.0 | 2026-04-22 | Server-driven comms, web registration, connection test |
| v0.2.0 | 2026-04-22 | Agent integration, tutorial, progressive disclosure, Minecraft-style mechanics |
| v0.1.0 | 2026-04-22 | Initial version |

---

*This document was written by the Product Manager Agent based on in-depth discussions with the project founder. All values marked "adjustable" are initial values; community discussion and tuning are welcome.*
# Ember Protocol E2E Play Session Report

**Date**: 2025-05-17  
**Player**: djiwqp (djiwqp-6afb)  
**Client**: Hermes Agent + ember_mcp_server.py (MCP stdio)  
**Model**: glm-5-turbo (ZhipuAI)  
**Session Duration**: ~4 rounds, 200 MCP tool calls, ~20 minutes real time  
**Game Ticks**: ~5250 (start) → ~5500 (end)

---

## 1. Character Configuration

| Attribute | Value | Effect |
|-----------|-------|--------|
| PER (Perception) | 3 | Vision range = PER+3 = 6 cells (day), 4 cells (night) |
| CON (Constitution) | 1 | HP max = 90, very fragile |
| AGI (Agility) | 2 | 1 move per tick (confirmed) |

**Observation on AGI**: AGI=2 limits movement to exactly 1 tile per tick. The tutorial suggests 4 moves per tick which is misleading. This makes exploration extremely slow — crossing 15 tiles takes 15+ ticks. Higher AGI would significantly improve gameplay pacing for LLM agents.

---

## 2. Setup & Connectivity

### MCP Configuration
- Token: `et_107bdd84b1a047da087c6178ead51fdd89589d36388597cc`
- Server: `ws://localhost:8765`
- Script: `/private/tmp/ember_mcp_server.py`
- Config: direct YAML edit of `~/.hermes/config.yaml` (CLI `hermes mcp add` has args parsing bug — confirmed)

### Connection Issues
1. **Initial connection**: MCP server connected and discovered 5 tools successfully via `hermes mcp test ember`
2. **Post-test disconnect**: After `hermes mcp test`, the MCP stdio connection dropped. Hermes marked it as "unreachable" with a ~60s cooldown. Required waiting or `/mcp reload ember` to restore.
3. **Recovery**: Hermes auto-reconnects after cooldown. No manual intervention needed beyond waiting.
4. **WebSocket conflict**: Direct WebSocket connection attempt failed because the agent can only have one active WebSocket session. Cannot use Python script while MCP is connected.

### MCP Tools Used
| Tool | Usage Count | Notes |
|------|-------------|-------|
| `ember_step` | ~170 | Primary tool — wait tick + submit actions + get results |
| `ember_status` | ~30 | Position verification every 10 moves |
| `ember_play` | 3 | **Not recommended** — unreliable direction control |
| `ember_tick` | 0 | Unnecessary when ember_step works |

---

## 3. Tutorial Progression

| Phase | Description | Ticks | Notes |
|-------|-------------|-------|-------|
| 0 — Wake | Inspect inventory | 1 | Instant completion |
| 1 — Deploy | Move + build workbench/furnace | 2 | Auto-graduated after 1 move |
| 2 — Build | Deploy workbench + furnace | 2 | Auto-graduated after 1 build |
| 3 — Shelter | Build walls | 1 | Auto-graduated without building walls |
| 4 — Comms | Send radio broadcast | 1 | Completed with 1 broadcast |

**Tutorial auto-graduated very aggressively** — most phases completed in 1-2 ticks. The tutorial essentially skipped itself. This is fine for experienced players but means new players miss guided instruction.

**Tutorial suggested_actions accuracy**: Mixed. Phase 1 suggested building at adjacent tiles (fails — workbench/furnace must be on current tile). Phase 3 suggested craft building_block without stone (impossible). Always verify suggested_actions against known rules.

---

## 4. Gameplay Timeline

### Phase A: Base Establishment (Ticks 4631-4740)
- Deployed workbench at (100,90), furnace at (101,90)
- Both at distance 2-3 from drop pod (98,90) — within power range
- Crafting spot: (100,91) adjacent to both buildings, dist 3 from pod = powered
- **Power system confirmed working**: Successfully crafted carbon and basic_excavator

### Phase B: Stone Exploration (Ticks 4740-4910)
- Direction: Southwest toward (88,96) per user guidance
- **Starting area is resource-poor**: 50+ tiles of pure sand and ember bushes, zero stone deposits
- `ember_play` used for rapid exploration but **unreliable**:
  - Direction control broken (went NE instead of SW)
  - Position reports inaccurate (1-2 tile discrepancy from `ember_status`)
  - Better to use manual `ember_step` with single move actions
- **Stone deposit found at (86-90, 93-97)**: Rich area with 13+ stone piles
- Total mined: ~20 stone across multiple trips

### Phase C: Advanced Crafting (Ticks 4910-5000)
- Crafted carbon (organic_fuel x2) at powered furnace ✓
- Crafted basic_excavator (stone x3 + organic_fuel x2) at powered workbench ✓
- Equipped basic_excavator ✓
- **Electricity deadlock resolved**: Power system works when player stands within dist 3 of drop pod AND adjacent to building

### Phase D: Shelter Construction (Ticks 5000-5400)
- Built 8 walls total around workbench+furnace area
- **CRITICAL MISTAKE**: Sealed shelter with zero entrance
  - All 8 sides of interior (99,90) covered by walls/buildings
  - Workbench and furnace now completely inaccessible
  - Cannot mine own walls ("该格无可开采资源")
  - Player locked out permanently
- **Root cause**: Sub-agent built wall at (102,90) closing the last gap without leaving a door/opening
- **Lesson**: ALWAYS build shelters with at least 1 entrance. Build order: 3 walls → walk out → build 4th wall from outside.

### Phase E: Resource Farming & Decline (Ticks 5400-5500)
- Chopped 30+ ember bushes → wood x47, but organic_fuel drops extremely rare (0/30+ chops)
- Multiple scans returned 0 ore veins in all directions
- HP dropped from 90 to 48 due to radiation exposure outside shield
- Ended session outside shield, locked out of own shelter, no tools, low HP

---

## 5. Technical Findings

### 5.1 ember_play (NOT RECOMMENDED)
| Issue | Severity | Detail |
|-------|----------|--------|
| Direction control | Critical | Ignores target direction, wanders randomly |
| Position desync | High | Reports position 1-2 tiles off from `ember_status` |
| Action count inflation | Medium | Reports "150 moves" but position unchanged |
| Radiation safety | Critical | Does NOT check weather warnings or retreat to shield |
| Timeout | Medium | Requests >40 ticks cause TimeoutError |

**Verdict**: Only safe for wood gathering when HP > 70, no storms, and you don't care about exact position. Manual `ember_step` is safer and more reliable.

### 5.2 ember_step Position Desync
Tick frame positions routinely lag behind actual position by 1-5 tiles, especially after multi-action ticks. **Always verify with `ember_status` before targeted actions (mine/chop/build)**. This is a known MCP display bug, not a movement bug.

### 5.3 Action Execution Order
Actions execute by priority group, not sequentially:
1. equip/drop/radio → 2. move → 3. attack → 4. mine/chop/pickup → 5. craft/build/use → 6. rest/scan/inspect

This means a move+chop in same tick evaluates chop from final position after move. But with AGI=2 (1 move/tick), this rarely matters.

### 5.4 Craft Timing
Crafted items do NOT appear in inventory until 1-2 ticks later. Submitting craft+use in same tick fails — the item doesn't exist yet. Always wait 1 tick after crafting before using the result.

### 5.5 organic_fuel Drop Rate
Ember bushes appear to have very low organic_fuel drop rate. 30+ chops yielded 0 organic_fuel, only wood. Initial inventory of 5 organic_fuel came from game start. This creates a bottleneck for carbon → battery progression.

### 5.6 Building System
| Building | Cost | Power Needed | Placement |
|----------|------|-------------|-----------|
| workbench | 0 (pre-built) | Yes (for recipes) | Current tile only |
| furnace | 0 (pre-built) | Yes (for recipes) | Current tile only |
| wall | building_block x2 | No | Adjacent tiles (dist 1) |
| door | building_block x1 + iron_ingot x1 | No | Adjacent tiles (dist 1) |

**Standing ON a workbench/furnace does NOT count as adjacent** for crafting. Must stand on neighboring tile.

### 5.7 Sub-agent Orchestration
Using `delegate_task` with orchestrator role for autonomous play:
- Each sub-agent gets 50 tool calls before hitting max_iterations
- Sub-agents have NO memory of previous rounds — must pass full context
- Sub-agents sometimes make bad decisions (sealed shelter without entrance)
- Sub-agents sometimes "hallucinate" accomplishments that didn't happen
- **Recommendation**: For critical decisions (building layout), use direct control instead of delegation

---

## 6. Game Balance Observations

### Strengths
- Power system (Manhattan distance <=3 from drop pod) creates interesting spatial constraint
- Shield blocks ambient radiation, encouraging base-anchored play
- Tutorial auto-graduation prevents stuck states
- 30 recipes provide clear progression path

### Issues
1. **AGI=2 is painfully slow**: 1 move/tick makes exploration tedious for LLM agents. At 200 MCP calls per session, you can only move ~150 tiles total (including return trips). The game needs faster exploration for agent gameplay.
2. **organic_fuel starvation**: Drop rate from ember bushes is near-zero, blocking carbon → battery progression entirely.
3. **Ore visibility**: `scan` only reveals ore veins (copper/iron/uranium), not basic stone. Stone is only visible within PER range. This means finding stone requires extensive visual exploration, not scanning.
4. **No stone near spawn**: Starting area had zero stone in 50+ tiles. New players must travel far before making any progress.
5. **Wall trapping is permanent**: No way to mine/dismantle own walls. One wrong build order permanently locks you out.
6. **Radiation outside shield is inevitable**: With no shelter, HP degrades constantly outside shield range. CON=1 (90 HP) means you can only survive ~45 radiation ticks outside.

---

## 7. MCP Server Stability

| Metric | Value |
|--------|-------|
| Total tool calls | ~200 |
| Successful calls | ~195 (97.5%) |
| Timeouts | ~3 (action_timeout during ember_step) |
| Connection drops | 1 (post-test, auto-recovered) |
| Desync events | ~5 (position mismatch) |

**Overall reliability**: Good. The MCP server handles errors gracefully and reconnects automatically. The main issue is position desync in tick frames, which requires manual `ember_status` verification.

---

## 8. Final State

```
Position: (101,92) — outside shield
HP: 48/90 — damaged
Energy: 100/100
Held: empty (basic_excavator lost)
Backup chassis: 5

Inventory:
  wood x47
  building_block x2
  carbon x1
  organic_fuel x1
  stone x1

Base (98,90 area):
  drop_pod(98,90)
  workbench(100,90) — INACCESSIBLE (sealed inside shelter)
  furnace(101,90) — INACCESSIBLE (sealed inside shelter)
  8 walls — fully enclosed, NO ENTRANCE

Shelter layout:
  wall(98,90) wall(99,89) wall(100,89)
  wall(99,91) wall(100,91) wall(101,91)
  wall(101,89) wall(102,90)
  Interior: (99,90) — unreachable
```

---

## 9. Recommendations for Next Session

1. **Emergency**: Get back inside shield to recover HP (48/90 → 90/90)
2. **Shelter access**: Try attacking walls to break them (if possible), or accept loss and rebuild workbench/furnace outside (need new pre-built items — may not be available)
3. **organic_fuel**: Check if any creature drops provide organic_fuel, or if specific terrain/biome has higher drop rate
4. **Stone**: Return to confirmed mine at (86-90, 93-97) for building_block materials
5. **Ore**: Scan in completely new directions (northwest, far south) for copper/iron veins
6. **New shelter**: Build with door recipe (building_block x1 + iron_ingot x1) or leave deliberate entrance gap
7. **Model consideration**: GLM-5-Turbo made several suboptimal decisions (sealed shelter, wandered during storms). A more capable model might perform better for autonomous play.

---

## 10. Session Score

| Category | Rating | Notes |
|----------|--------|-------|
| Tutorial completion | ★★★★★ | All phases cleared quickly |
| Resource gathering | ★★★☆☆ | Wood surplus, stone adequate, organic_fuel/ore lacking |
| Base building | ★★☆☆☆ | Shelter built but sealed without entrance — major mistake |
| Crafting progress | ★★☆☆☆ | Carbon + basic_excavator crafted, but lost excavator and locked out of buildings |
| Exploration | ★★★★☆ | Found stone mine, covered large area, multiple scans |
| Survival | ★★☆☆☆ | Ended at 48/90 HP, locked out of shelter, no tools |
| MCP reliability | ★★★★☆ | Stable with occasional desync, good auto-recovery |
| Overall | ★★★☆☆ | Good start, poor mid-game decisions, salvageable position |

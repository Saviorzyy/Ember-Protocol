"""Ember Protocol — Snapshot Renderer
Generate map/observer screenshots using PIL.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont
from server.engine.world import WorldMap, get_zone, DayNightCycle
from server.engine.game import GameEngine
from server.models import Attributes, Position, TerrainType, CoverType, DayPhase

# ─── Color Palette ────────────────────────────────────────────────

TERRAIN_COLORS = {
    TerrainType.FLAT:     (139, 115, 85),
    TerrainType.ROCK:     (107, 114, 128),
    TerrainType.SAND:     (194, 178, 128),
    TerrainType.HIGHLAND: (74, 222, 128),
    TerrainType.TRENCH:   (30, 58, 95),
    TerrainType.WATER:    (59, 130, 246),
}

COVER_COLORS = {
    CoverType.VEG_ASHBRUSH:  (34, 197, 94),
    CoverType.VEG_GREYTREE:  (22, 163, 74),
    CoverType.VEG_WALLMOSS:  (21, 128, 61),
    CoverType.ORE_STONE:     (168, 162, 158),
    CoverType.ORE_ORGANIC:   (217, 119, 6),
    CoverType.ORE_COPPER:    (249, 115, 22),
    CoverType.ORE_IRON:      (239, 68, 68),
    CoverType.ORE_URANIUM:   (168, 85, 247),
    CoverType.ORE_GOLD:      (252, 211, 77),
    CoverType.FLOOR:         (212, 212, 216),
    CoverType.RUBBLE:        (120, 113, 108),
}

AGENT_COLORS = [
    (0, 212, 170), (0, 153, 255), (245, 158, 11),
    (239, 68, 68), (139, 92, 246), (236, 72, 153),
]


def render_map_snapshot(world: WorldMap, filename: str, tile_size: int = 6,
                        agents=None, zoom_region=None):
    """Render full map or a region to PNG."""
    if zoom_region:
        x0, y0, x1, y1 = zoom_region
    else:
        x0, y0, x1, y1 = 0, 0, world.width, world.height

    w = (x1 - x0) * tile_size
    h = (y1 - y0) * tile_size

    img = Image.new('RGB', (w, h), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    # Draw tiles
    for y in range(y0, y1):
        for x in range(x0, x1):
            tile = world.get_tile(x, y)
            if not tile:
                continue
            px = (x - x0) * tile_size
            py = (y - y0) * tile_size

            # L1 terrain
            color = TERRAIN_COLORS.get(tile.l1, (50, 50, 50))
            draw.rectangle([px, py, px + tile_size - 1, py + tile_size - 1], fill=color)

            # L2 cover
            if tile.l2:
                cc = COVER_COLORS.get(tile.l2)
                if cc:
                    # Slightly smaller rectangle for cover
                    draw.rectangle([px + 1, py + 1, px + tile_size - 2, py + tile_size - 2], fill=cc)

    # Draw agents
    if agents:
        for i, agent in enumerate(agents):
            if not agent.is_alive():
                continue
            ax = (agent.position.x - x0) * tile_size + tile_size // 2
            ay = (agent.position.y - y0) * tile_size + tile_size // 2
            r = max(2, tile_size // 3)
            color = AGENT_COLORS[i % len(AGENT_COLORS)]
            draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=color)
            # White outline
            draw.ellipse([ax - r - 1, ay - r - 1, ax + r + 1, ay + r + 1], outline=(255, 255, 255), width=1)

    img.save(filename)
    print(f"Saved: {filename} ({w}x{h})")
    return img


def render_observer_snapshot(engine: GameEngine, filename: str, tile_size: int = 8):
    """Render a detailed observer view with HUD."""
    # Full map
    map_w = engine.world.width * tile_size
    map_h = engine.world.height * tile_size

    # Total image with HUD panel
    panel_w = 280
    total_w = map_w + panel_w
    total_h = max(map_h, 600)

    img = Image.new('RGB', (total_w, total_h), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    # Render map area
    map_img = render_map_snapshot(engine.world, "/tmp/_map_tmp.png", tile_size,
                                  list(engine.agents.values()))
    img.paste(map_img, (0, 0))

    # Draw HUD panel
    px = map_w + 10
    # Panel background
    draw.rectangle([map_w, 0, total_w, total_h], fill=(17, 24, 39))
    draw.line([map_w, 0, map_w, total_h], fill=(55, 65, 81), width=1)

    # Title
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9)
    except:
        font = ImageFont.load_default()
        font_sm = font

    draw.text((px, 10), "EMBER PROTOCOL", fill=(0, 212, 170), font=font)
    draw.text((px, 30), f"Tick: {engine.current_tick}", fill=(249, 250, 251), font=font_sm)
    draw.text((px, 45), f"Day Phase: {engine.day_night.current_phase.value}", fill=(245, 158, 11), font=font_sm)
    draw.text((px, 60), f"Weather: {engine.weather.current.value}", fill=(139, 92, 246), font=font_sm)

    # Agents
    draw.text((px, 85), "AGENTS", fill=(0, 212, 170), font=font)
    y = 105
    for i, (aid, agent) in enumerate(engine.agents.items()):
        if not agent.is_alive():
            continue
        color = AGENT_COLORS[i % len(AGENT_COLORS)]
        draw.rectangle([px, y, px + 8, y + 8], fill=color)
        draw.text((px + 12, y), f"{agent.name}", fill=(249, 250, 251), font=font_sm)
        y += 15
        # HP bar
        bar_w = 100
        bar_h = 4
        draw.rectangle([px + 12, y, px + 12 + bar_w, y + bar_h], fill=(31, 41, 55))
        hp_w = int(bar_w * agent.hp / agent.max_hp)
        draw.rectangle([px + 12, y, px + 12 + hp_w, y + bar_h], fill=(239, 68, 68))
        y += 8
        # Energy bar
        draw.rectangle([px + 12, y, px + 12 + bar_w, y + bar_h], fill=(31, 41, 55))
        en_w = int(bar_w * agent.energy / agent.max_energy)
        draw.rectangle([px + 12, y, px + 12 + en_w, y + bar_h], fill=(245, 158, 11))
        y += 12
        draw.text((px + 12, y), f"Pos: ({agent.position.x},{agent.position.y}) HP:{agent.hp} E:{agent.energy}",
                   fill=(156, 163, 175), font=font_sm)
        y += 18

    # Legend
    y = max(y + 10, total_h - 180)
    draw.text((px, y), "TERRAIN", fill=(0, 212, 170), font=font)
    y += 18
    for terrain, color in TERRAIN_COLORS.items():
        draw.rectangle([px, y, px + 10, y + 10], fill=color)
        draw.text((px + 14, y), terrain.value, fill=(156, 163, 175), font=font_sm)
        y += 14

    img.save(filename)
    print(f"Saved: {filename} ({total_w}x{total_h})")
    return img


# ─── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("snapshots", exist_ok=True)

    print("=== Ember Protocol Snapshot Renderer ===\n")

    # 1. Generate world
    print("1. Generating world (100x100, seed=42)...")
    world = WorldMap(width=100, height=100, seed=42)
    world.generate()

    # 2. Full map snapshot
    print("\n2. Rendering full map...")
    render_map_snapshot(world, "snapshots/01-full-map.png", tile_size=6)

    # 3. Map region (center area, zoomed)
    print("\n3. Rendering center region (zoomed)...")
    render_map_snapshot(world, "snapshots/02-center-zoom.png", tile_size=16,
                        zoom_region=(35, 35, 65, 65))

    # 4. Create game engine with agents
    print("\n4. Creating game engine with test agents...")
    engine = GameEngine(map_width=100, map_height=100, seed=42)

    # Register test agents
    builds = [
        ("Scout", Attributes(2, 1, 3)),
        ("Heavy", Attributes(3, 2, 1)),
        ("Striker", Attributes(1, 3, 2)),
        ("Balanced", Attributes(2, 2, 2)),
    ]
    for name, attrs in builds:
        agent = engine.register_agent(name, attrs, "http://test", "key")
        # Spread agents slightly
        agent.position = Position(
            agent.position.x + hash(name) % 6 - 3,
            agent.position.y + hash(name + "x") % 6 - 3,
        )
        agent.inventory.add_item(__import__('server.models', fromlist=['ItemInstance']).ItemInstance(item_id="basic_excavator"), __import__('server.models.items', fromlist=['ITEM_DB']).ITEM_DB)
        agent.equipment.main_hand = __import__('server.models', fromlist=['ItemInstance']).ItemInstance(item_id="basic_excavator")

    # 5. Observer view
    print("\n5. Rendering observer view...")
    render_observer_snapshot(engine, "snapshots/03-observer-view.png", tile_size=8)

    # 6. Day/Night cycle comparison
    print("\n6. Rendering day/night comparison...")
    img_day = render_map_snapshot(world, "snapshots/04-day.png", tile_size=6,
                                  agents=list(engine.agents.values()),
                                  zoom_region=(30, 30, 70, 70))

    # Create night version (darker)
    from PIL import ImageEnhance
    img_night = ImageEnhance.Brightness(img_day).enhance(0.4)
    img_night.save("snapshots/05-night.png")
    print("Saved: snapshots/05-night.png")

    # 7. Zone distribution
    print("\n7. Rendering zone distribution...")
    zone_colors = {
        "center": (100, 200, 100),
        "T1": (150, 200, 100),
        "T2": (200, 200, 100),
        "T3": (200, 150, 100),
        "T4": (200, 100, 100),
    }
    zone_img = Image.new('RGB', (400, 400), (10, 14, 23))
    zone_draw = ImageDraw.Draw(zone_img)
    for y in range(100):
        for x in range(100):
            zone = get_zone(y, 100)
            color = zone_colors.get(zone, (50, 50, 50))
            zone_draw.rectangle([x*4, y*4, x*4+3, y*4+3], fill=color)
    zone_img.save("snapshots/06-zone-map.png")
    print("Saved: snapshots/06-zone-map.png")

    print("\n=== All snapshots generated! ===")
    print("Files in snapshots/:")
    for f in sorted(os.listdir("snapshots")):
        size = os.path.getsize(f"snapshots/{f}")
        print(f"  {f} ({size:,} bytes)")

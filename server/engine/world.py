"""Ember Protocol — World Engine
Map generation, terrain system, weather, day/night cycle.
Based on PRD v0.9.1, Sections 7.0, 7.8, 7.9, 7.16

v0.9.4: Rewrote trench generation — replaced contour-line distance method
        (which created map-splitting straight lines) with discrete wandering
        trench segments: short curved snakes with gaps, guaranteed map
        connectivity via BFS validation.
v0.9.3: Fixed terrain straight-line artifacts (zone-blended noise with
        smooth gradient transitions instead of hard zone boundaries),
        fixed diamond-shaped ore veins (Euclidean distance + random
        perturbation instead of Manhattan distance).
"""

from __future__ import annotations
import math
import random
from typing import Optional

from server.models import (
    Tile, TerrainType, CoverType, WeatherType, DayPhase, Position,
    DAY_CYCLE_TICKS, DAY_TICKS, DUSK_TICKS, NIGHT_TICKS, DAWN_TICKS,
    ENCLOSURE_MAX_TILES,
)


# ─── Perlin-like Noise (improved) ────────────────────────────────

def _hash_coord(x: int, y: int, seed: int) -> float:
    """Deterministic pseudo-random for a coordinate.
    Uses fast integer hash instead of MD5 for 400x400 performance."""
    h = seed
    h ^= x * 0x9E3779B97F4A7C15
    h ^= y * 0x517CC1B727220A95
    h ^= (h >> 33)
    h *= 0xFF51AFD7ED558CCD
    h ^= (h >> 33)
    h *= 0xC4CEB9FE1A85EC53
    h ^= (h >> 33)
    return (h & 0x7FFFFFFF) / 0x7FFFFFFF


def _smooth_noise(x: float, y: float, seed: int, scale: float) -> float:
    """Value noise with quintic interpolation for natural terrain."""
    sx = x * scale
    sy = y * scale
    x0, y0 = int(math.floor(sx)), int(math.floor(sy))
    fx = sx - x0
    fy = sy - y0
    # Quintic smoothstep (eliminates grid artifacts)
    fx = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    fy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)
    n00 = _hash_coord(x0, y0, seed)
    n10 = _hash_coord(x0 + 1, y0, seed)
    n01 = _hash_coord(x0, y0 + 1, seed)
    n11 = _hash_coord(x0 + 1, y0 + 1, seed)
    nx0 = n00 * (1 - fx) + n10 * fx
    nx1 = n01 * (1 - fx) + n11 * fx
    return nx0 * (1 - fy) + nx1 * fy


def _octave_noise(x: int, y: int, seed: int, scale: float, octaves: int = 4,
                  persistence: float = 0.5, lacunarity: float = 2.0) -> float:
    """Multi-octave noise with configurable persistence and lacunarity."""
    total = 0.0
    amp = 1.0
    freq = 1.0
    max_val = 0.0
    for i in range(octaves):
        total += _smooth_noise(x * freq, y * freq, seed, scale) * amp
        max_val += amp
        amp *= persistence
        freq *= lacunarity
    return total / max_val


def _anisotropic_noise(x: int, y: int, seed: int,
                       scale_x: float, scale_y: float,
                       angle: float = 0.0,
                       octaves: int = 4, persistence: float = 0.5,
                       lacunarity: float = 2.0) -> float:
    """Multi-octave noise with anisotropic scaling for elongated features.
    Creates features stretched in one direction — ideal for trenches,
    rivers, and other linear terrain features.

    Args:
        x, y: Integer tile coordinates
        seed: Random seed for deterministic generation
        scale_x: Noise scale along the (rotated) x-axis (smaller = wider)
        scale_y: Noise scale along the (rotated) y-axis (smaller = wider)
        angle: Rotation in radians for the elongation axis
        octaves, persistence, lacunarity: Same as _octave_noise
    """
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rx = x * cos_a - y * sin_a
    ry = x * sin_a + y * cos_a

    total = 0.0
    amp = 1.0
    freq = 1.0
    max_val = 0.0

    for i in range(octaves):
        sx = rx * freq * scale_x
        sy = ry * freq * scale_y

        x0 = int(math.floor(sx))
        y0 = int(math.floor(sy))
        fx = sx - x0
        fy = sy - y0
        fx = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
        fy = fy * fy * fy * (fy * (fy * 6 - 15) + 10)

        n00 = _hash_coord(x0, y0, seed + i * 1000)
        n10 = _hash_coord(x0 + 1, y0, seed + i * 1000)
        n01 = _hash_coord(x0, y0 + 1, seed + i * 1000)
        n11 = _hash_coord(x0 + 1, y0 + 1, seed + i * 1000)

        nx0 = n00 * (1 - fx) + n10 * fx
        nx1 = n01 * (1 - fx) + n11 * fx
        val = nx0 * (1 - fy) + nx1 * fy

        total += val * amp
        max_val += amp
        amp *= persistence
        freq *= lacunarity

    return total / max_val


# ─── Zone System ──────────────────────────────────────────────────

def get_zone(y: int, map_height: int) -> str:
    """Determine zone by latitude (north-south).
    Center is safe, edges are dangerous."""
    center = map_height // 2
    dist = abs(y - center)
    ratio = dist / center
    if ratio < 0.15:
        return "center"
    elif ratio < 0.35:
        return "T1"
    elif ratio < 0.55:
        return "T2"
    elif ratio < 0.75:
        return "T3"
    else:
        return "T4"


def _zone_blend(y: int, map_height: int) -> dict[str, float]:
    """Compute smooth zone weights for a given y coordinate.
    Instead of hard zone boundaries, we blend between adjacent zones
    to eliminate straight-line terrain transitions.

    Returns a dict of {zone_name: weight} where weights sum to ~1.0.
    The weight transitions smoothly using a cosine curve over a
    transition band of ±10% of map height around each boundary."""
    center = map_height // 2
    dist = abs(y - center)
    ratio = dist / center

    # Zone boundary ratios
    bounds = [0.15, 0.35, 0.55, 0.75]
    zones = ["center", "T1", "T2", "T3", "T4"]

    # Transition width: 10% of half-height = 5% of map
    tw = 0.10

    # Find which zone we're in and compute blend
    for i, b in enumerate(bounds):
        if ratio < b - tw:
            # Fully inside zone i
            return {zones[i]: 1.0}
        elif ratio < b + tw:
            # In transition zone between zone i and zone i+1
            t = (ratio - (b - tw)) / (2 * tw)
            # Smooth cosine interpolation
            t = 0.5 - 0.5 * math.cos(t * math.pi)
            return {zones[i]: 1.0 - t, zones[i + 1]: t}

    # Past last boundary
    return {zones[-1]: 1.0}


# Terrain probability tables by zone
# Terrain weights control flat/sand/rock distribution only.
# Highland and trench are handled by separate noise thresholds
# (elevation noise for highland, anisotropic noise for trench).
TERRAIN_WEIGHTS = {
    "center": {"flat": 0.65, "sand": 0.25, "rock": 0.10},
    "T1":     {"flat": 0.55, "sand": 0.28, "rock": 0.17},
    "T2":     {"flat": 0.40, "sand": 0.25, "rock": 0.35},
    "T3":     {"flat": 0.22, "sand": 0.18, "rock": 0.60},
    "T4":     {"flat": 0.12, "sand": 0.12, "rock": 0.76},
}

# L2 cover probabilities by zone
COVER_WEIGHTS = {
    "center": {
        "veg_ashbrush": 0.13, "veg_greytree": 0.06, "veg_wallmoss": 0.03,
        "ore_stone": 0.08, "ore_organic": 0.07,
        "ore_copper": 0.004,
        "ore_iron": 0.002,
        "ore_uranium": 0.0005,
        "ore_gold": 0.0005,
    },
    "T1": {
        "veg_ashbrush": 0.11, "veg_greytree": 0.06, "veg_wallmoss": 0.02,
        "ore_stone": 0.05, "ore_organic": 0.04,
        "ore_copper": 0.005,
        "ore_iron": 0.002,
        "ore_uranium": 0.001,
        "ore_gold": 0.001,
    },
    "T2": {
        "veg_ashbrush": 0.07, "veg_greytree": 0.09, "veg_wallmoss": 0.04,
        "ore_stone": 0.04, "ore_organic": 0.03,
        "ore_copper": 0.006,
        "ore_iron": 0.004,
        "ore_uranium": 0.002,
        "ore_gold": 0.001,
    },
    "T3": {
        "veg_ashbrush": 0.04, "veg_greytree": 0.06, "veg_wallmoss": 0.03,
        "ore_stone": 0.03, "ore_organic": 0.02,
        "ore_copper": 0.005,
        "ore_iron": 0.006,
        "ore_uranium": 0.003,
        "ore_gold": 0.002,
    },
    "T4": {
        "veg_ashbrush": 0.02, "veg_greytree": 0.03, "veg_wallmoss": 0.01,
        "ore_stone": 0.02, "ore_organic": 0.01,
        "ore_copper": 0.004,
        "ore_iron": 0.005,
        "ore_uranium": 0.004,
        "ore_gold": 0.003,
    },
}

# L2 cover yield amounts
COVER_YIELDS = {
    "veg_ashbrush": ("wood", 1, 3),
    "veg_greytree": ("wood", 2, 2),
    "veg_wallmoss": ("wood", 1, 1),
    "ore_stone": ("stone", 3, 6),
    "ore_organic": ("organic_fuel", 2, 5),
    "ore_copper": ("raw_copper", 2, 4),
    "ore_iron": ("raw_iron", 2, 4),
    "ore_uranium": ("uranium_ore", 1, 2),
    "ore_gold": ("raw_gold", 1, 2),
}

# Cover L1 compatibility — expanded for more natural placement
COVER_L1_COMPAT = {
    "veg_ashbrush": [TerrainType.FLAT, TerrainType.SAND, TerrainType.HIGHLAND],
    "veg_greytree": [TerrainType.ROCK, TerrainType.HIGHLAND, TerrainType.FLAT],
    "veg_wallmoss": [TerrainType.TRENCH, TerrainType.ROCK],
    "ore_stone": [TerrainType.ROCK, TerrainType.TRENCH, TerrainType.HIGHLAND],
    "ore_organic": [TerrainType.FLAT, TerrainType.SAND],
    "ore_copper": [TerrainType.ROCK, TerrainType.HIGHLAND, TerrainType.TRENCH],
    "ore_iron": [TerrainType.ROCK, TerrainType.TRENCH, TerrainType.HIGHLAND],
    "ore_uranium": [TerrainType.ROCK, TerrainType.TRENCH],
    "ore_gold": [TerrainType.ROCK, TerrainType.TRENCH, TerrainType.HIGHLAND],
}

# Zone radiation probability per tick
ZONE_RADIATION_PROB = {
    "center": 0.0, "T1": 0.0, "T2": 0.05, "T3": 0.15, "T4": 0.30,
}


# ─── Map Generation (Overhauled v2) ─────────────────────────────

class WorldMap:
    def __init__(self, width: int = 400, height: int = 400, seed: int = 42):
        self.width = width
        self.height = height
        self.seed = seed
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.enclosures: dict[str, set[tuple[int, int]]] = {}
        self._enclosure_cache: dict[tuple[int, int], Optional[str]] = {}
        self._next_enclosure_id = 0
        self._buildings_ref: Optional[dict] = None
        # Pre-computed noise fields for coherent terrain
        self._terrain_noise: Optional[dict[tuple[int, int], float]] = None
        self._moisture_noise: Optional[dict[tuple[int, int], float]] = None
        self._elevation_noise: Optional[dict[tuple[int, int], float]] = None
        self._cover_noise: Optional[dict[tuple[int, int], float]] = None

    def set_buildings_ref(self, buildings: dict):
        """Set reference to buildings dict for wall/door type lookup."""
        self._buildings_ref = buildings

    def generate(self):
        """Generate the full map with coherent terrain and ore veins."""
        # Phase 1: Generate coherent terrain noise
        self._generate_noise_fields()

        # Phase 2: Generate terrain (L1) for all tiles using blended zones
        # (no trenches yet — they are placed separately)
        for y in range(self.height):
            for x in range(self.width):
                tile = self._generate_terrain(x, y)
                self.tiles[(x, y)] = tile

        # Phase 3: Place trenches as discrete wandering segments
        # This MUST happen before ore veins so trenches get proper L2 cover
        self._generate_trenches()

        # Phase 4: Place ore veins (metal surrounded by stone, irregular shapes)
        self._place_ore_veins()

        # Phase 5: Place vegetation (L2 for non-ore tiles)
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[(x, y)]
                if tile.l2 is None:  # Not already set by ore vein
                    self._place_vegetation(tile, x, y)

    def _generate_noise_fields(self):
        """Pre-compute noise values for coherent terrain generation.
        Uses low-frequency noise with many octaves for large-scale features,
        creating natural biome-like regions instead of scattered pixels.
        
        Critical fix: Multi-octave noise tends to cluster around 0.5 
        (central limit theorem), which compresses terrain weight mappings
        and causes large uniform areas. We apply histogram equalization
        to spread noise values uniformly across [0, 1].
        
        Trenches are NO LONGER generated from noise. Instead they are
        placed as discrete wandering segments after terrain generation
        (see _generate_trenches)."""
        self._terrain_noise = {}
        self._moisture_noise = {}
        self._elevation_noise = {}
        self._cover_noise = {}

        # Scale determines feature size: lower = larger features
        # 0.005 gives ~80-tile wide biomes on a 400x400 map
        terrain_scale = 0.005
        moisture_scale = 0.007
        elevation_scale = 0.006
        cover_scale = 0.04  # Higher freq for diverse local cover (~25-tile features)

        # Generate raw noise values first (before equalization)
        raw_terrain = {}
        raw_moisture = {}
        raw_elevation = {}
        raw_cover = {}

        for y in range(self.height):
            for x in range(self.width):
                raw_terrain[(x, y)] = _octave_noise(
                    x, y, self.seed, terrain_scale, octaves=6, persistence=0.35
                )
                raw_moisture[(x, y)] = _octave_noise(
                    x, y, self.seed + 1000, moisture_scale, octaves=5, persistence=0.45
                )
                raw_elevation[(x, y)] = _octave_noise(
                    x, y, self.seed + 2000, elevation_scale, octaves=5, persistence=0.45
                )
                raw_cover[(x, y)] = _octave_noise(
                    x, y, self.seed + 3000, cover_scale, octaves=4, persistence=0.5
                )

        # Apply histogram equalization to terrain AND cover noise
        # (both use cumulative weight mapping, so need uniform distribution).
        # Elevation and moisture use fixed thresholds, so raw values are fine.
        self._terrain_noise = self._equalize(raw_terrain)
        self._moisture_noise = raw_moisture
        self._elevation_noise = raw_elevation
        self._cover_noise = self._equalize(raw_cover)

    @staticmethod
    def _equalize(noise_dict: dict) -> dict:
        """Histogram equalization: maps noise values to uniform distribution.
        Preserves the spatial structure (same relative ordering) but spreads
        values evenly across [0, 1] so cumulative weight thresholds work correctly."""
        if not noise_dict:
            return noise_dict
        
        # Sort all values
        sorted_items = sorted(noise_dict.items(), key=lambda item: item[1])
        n = len(sorted_items)
        
        # Map each value to its rank / total (uniform distribution)
        result = {}
        for rank, (key, _val) in enumerate(sorted_items):
            result[key] = (rank + 0.5) / n  # +0.5 avoids exact 0 and 1
        
        return result

    def _generate_terrain(self, x: int, y: int) -> Tile:
        """Generate L1 terrain using pre-computed noise with smooth zone blending.
        
        Key design:
        - Trench: NOT generated here — placed separately by _generate_trenches()
        - Highland: elevation noise creates blobby elevated areas
        - Flat/Sand/Rock: weight-based selection from zone-blended probabilities
        - Water: moisture threshold in outer zones only
        """
        # Get blended zone weights for this y coordinate
        zone_weights = _zone_blend(y, self.height)

        # Blend terrain probabilities from all contributing zones
        blended = {}
        for zone, zw in zone_weights.items():
            for terrain_str, tw in TERRAIN_WEIGHTS[zone].items():
                blended[terrain_str] = blended.get(terrain_str, 0.0) + tw * zw

        base_noise = self._terrain_noise[(x, y)]
        moisture = self._moisture_noise[(x, y)]
        elevation = self._elevation_noise[(x, y)]

        # Water: only in outer zones where moisture is very high
        outer_weight = sum(zw for zone, zw in zone_weights.items() if zone in ("T2", "T3", "T4"))
        if moisture > 0.82 and outer_weight > 0.5:
            return Tile(x=x, y=y, l1=TerrainType.WATER)

        # Zone factor: 0 for center, increasing for outer zones
        zone_factor_map = {"center": 0, "T1": 0.02, "T2": 0.04, "T3": 0.06, "T4": 0.08}
        zf = sum(zone_factor_map.get(zone, 0) * zw for zone, zw in zone_weights.items())

        # Highland: blobby features via elevation noise
        # Lower threshold in outer zones → more highland there
        if elevation > 0.83 - zf * 0.3:
            l1 = TerrainType.HIGHLAND
        else:
            l1 = self._pick_terrain(base_noise, blended)

        return Tile(x=x, y=y, l1=l1)

    # ─── Trench Generation (Wandering Segments) ──────────────────────

    def _generate_trenches(self):
        """Place trenches as discrete wandering segments (short curved snakes).
        
        DESIGN PRINCIPLES:
        1. Each trench is a SHORT segment (15-40 tiles), not a continuous line
        2. Segments WANDER (direction drifts gradually), never perfectly straight
        3. GAPS are built in: every N tiles, one tile is skipped, ensuring
           the trench never forms a complete barrier
        4. Trenches are THICKER in outer zones (1-3 tiles wide)
        5. BFS CONNECTIVITY CHECK after placement: if any trench cuts off
           a region from the center, those tiles are reverted to non-trench
        6. Total trench coverage targets ~4-6% of the map
        
        This replaces the old contour-line distance method which created
        long straight lines that partitioned the entire map.
        """
        rng = random.Random(self.seed + 7000)

        # Configuration by zone
        # More segments = more scattered; longer segments = more elongated
        # Width 1 keeps them thin; T4 gets width 2 for wider crags
        # Counts are calibrated for a ~200x200 map; larger maps scale proportionally
        base_area = 200 * 200
        area_scale = max(1, round((self.width * self.height) / base_area))

        zone_config = {
            "center": {"count": (2, 4),  "length": (20, 35), "width": 1, "gap_every": 5},
            "T1":     {"count": (3, 5),  "length": (25, 45), "width": 1, "gap_every": 6},
            "T2":     {"count": (4, 7),  "length": (30, 55), "width": 1, "gap_every": 7},
            "T3":     {"count": (5, 8),  "length": (35, 65), "width": 1, "gap_every": 8},
            "T4":     {"count": (6, 10), "length": (40, 80), "width": 2, "gap_every": 8},
        }

        # Collect all candidate trench tiles (zone → list of positions)
        all_trench_tiles: set[tuple[int, int]] = set()
        # Track segment start points to avoid overlap
        used_starts: set[tuple[int, int]] = set()

        for zone_name, cfg in zone_config.items():
            num_segments = rng.randint(*cfg["count"]) * area_scale
            seg_len_range = cfg["length"]
            seg_width = cfg["width"]
            gap_every = cfg["gap_every"]

            # Find y-range for this zone
            zone_y_ranges = self._zone_y_ranges(zone_name)
            if not zone_y_ranges:
                continue

            for _ in range(num_segments * 4):  # Oversample to get enough valid starts
                if num_segments <= 0:
                    break
                # Pick random start point within the zone
                start_y = rng.choice(zone_y_ranges)
                start_x = rng.randint(20, self.width - 20)
                start_pos = (start_x, start_y)

                # Ensure starts are far enough apart (avoid blobby overlap)
                min_start_dist = max(15, min(self.width, self.height) // 15)
                too_close = False
                for us in used_starts:
                    if abs(us[0] - start_x) + abs(us[1] - start_y) < min_start_dist:
                        too_close = True
                        break
                if too_close:
                    continue

                # Generate a wandering segment
                segment_tiles = self._wander_segment(
                    start_x, start_y, rng,
                    length_range=seg_len_range,
                    width=seg_width,
                    gap_every=gap_every,
                )

                # Only keep tiles that are on passable terrain
                valid_tiles = set()
                for pos in segment_tiles:
                    tile = self.tiles.get(pos)
                    if tile and tile.l1 != TerrainType.WATER and tile.l1 != TerrainType.TRENCH:
                        valid_tiles.add(pos)

                if len(valid_tiles) >= 5:  # Only count segments that produced enough tiles
                    all_trench_tiles.update(valid_tiles)
                    used_starts.add(start_pos)
                    num_segments -= 1

        # Apply trench tiles
        for (x, y) in all_trench_tiles:
            self.tiles[(x, y)].l1 = TerrainType.TRENCH

        # BFS connectivity check — ensure the map isn't split
        self._ensure_connectivity(all_trench_tiles)

    def _zone_y_ranges(self, zone_name: str) -> list[int]:
        """Return list of y coordinates that belong to the given zone."""
        result = []
        for y in range(self.height):
            zw = _zone_blend(y, self.height)
            if zone_name in zw and zw[zone_name] > 0.5:
                result.append(y)
        return result

    def _wander_segment(
        self,
        start_x: int, start_y: int,
        rng: random.Random,
        length_range: tuple[int, int] = (15, 30),
        width: int = 1,
        gap_every: int = 4,
    ) -> set[tuple[int, int]]:
        """Generate a wandering trench segment.
        
        The segment starts at (start_x, start_y) and walks in a direction
        that gradually drifts, creating a curved path. Every gap_every tiles,
        one tile is skipped to ensure the trench has gaps (no complete barriers).
        
        Width > 1 adds perpendicular tiles for wider trenches.
        """
        length = rng.randint(*length_range)
        # Initial direction in radians
        angle = rng.uniform(0, 2 * math.pi)
        # How much the angle can drift per step (radians)
        # Small drift = more elongated; larger drift = more curvy/wandering
        max_drift = rng.uniform(0.08, 0.20)

        cx, cy = float(start_x), float(start_y)
        tiles: set[tuple[int, int]] = set()
        step_count = 0

        for i in range(length):
            # Skip every gap_every-th tile to create gaps
            if gap_every > 0 and i > 0 and i % gap_every == 0:
                # Skip this tile, but still advance position
                angle += rng.uniform(-max_drift, max_drift)
                cx += math.cos(angle)
                cy += math.sin(angle)
                step_count += 1
                continue

            ix, iy = int(round(cx)), int(round(cy))

            # Place center tile
            if self.in_bounds(ix, iy):
                tiles.add((ix, iy))

                # Add width: perpendicular tiles
                if width > 1:
                    perp_angle = angle + math.pi / 2
                    half_w = width // 2
                    for w in range(1, half_w + 1):
                        for sign in (1, -1):
                            px = ix + int(round(sign * w * math.cos(perp_angle)))
                            py = iy + int(round(sign * w * math.sin(perp_angle)))
                            if self.in_bounds(px, py):
                                tiles.add((px, py))

            # Advance with drift
            angle += rng.uniform(-max_drift, max_drift)
            cx += math.cos(angle)
            cy += math.sin(angle)
            step_count += 1

        return tiles

    def _ensure_connectivity(self, trench_tiles: set[tuple[int, int]]):
        """BFS connectivity check: ensure the map is not partitioned by trenches.
        
        Strategy:
        1. BFS from center of map on non-trench, non-water tiles
        2. Find all reachable tiles
        3. Any non-trench, non-water tile NOT reached means the map is split
        4. Find "bridge" trench tiles adjacent to unreachable regions and revert them
        5. Repeat until the map is fully connected
        
        This is more efficient than checking every trench tile individually.
        """
        max_iterations = 10  # Safety limit
        
        for _iteration in range(max_iterations):
            # BFS from center
            center = (self.width // 2, self.height // 2)
            # If center is trench/water, find nearest non-trench/non-water tile
            start = self._find_nearest_passable(center)
            if not start:
                return  # Entire map is impassable? Shouldn't happen

            reachable = self._bfs_passable(start)

            # Check if all non-trench, non-water tiles are reachable
            unreachable = set()
            for y in range(self.height):
                for x in range(self.width):
                    pos = (x, y)
                    tile = self.tiles[pos]
                    if (tile.l1 != TerrainType.TRENCH
                            and tile.l1 != TerrainType.WATER
                            and pos not in reachable):
                        unreachable.add(pos)

            if not unreachable:
                return  # Map is fully connected

            # Find trench tiles that border unreachable regions
            # These are "cut points" — reverting them opens paths
            bridge_candidates: dict[tuple[int, int], int] = {}
            for pos in unreachable:
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = pos[0] + dx, pos[1] + dy
                    npos = (nx, ny)
                    if npos in trench_tiles:
                        # Count how many unreachable tiles this bridge would connect
                        bridge_candidates[npos] = bridge_candidates.get(npos, 0) + 1

            if not bridge_candidates:
                # No bridge candidates — revert ALL trench tiles adjacent to
                # unreachable regions by expanding search to diagonal neighbors
                for pos in unreachable:
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = pos[0] + dx, pos[1] + dy
                            npos = (nx, ny)
                            if npos in trench_tiles:
                                bridge_candidates[npos] = bridge_candidates.get(npos, 0) + 1

            if not bridge_candidates:
                return  # No bridges to remove

            # Revert the most impactful bridge tiles
            # Use more aggressive threshold: top 30% or at least 5
            sorted_bridges = sorted(bridge_candidates.items(), key=lambda x: -x[1])
            num_to_revert = max(5, len(sorted_bridges) * 3 // 10)
            for pos, _count in sorted_bridges[:num_to_revert]:
                tile = self.tiles[pos]
                # Revert to the most common surrounding non-trench terrain
                tile.l1 = self._most_common_neighbor_terrain(pos)
                trench_tiles.discard(pos)

    def _find_nearest_passable(self, pos: tuple[int, int]) -> Optional[tuple[int, int]]:
        """Find nearest non-trench, non-water tile from pos."""
        # Simple spiral search
        for radius in range(1, max(self.width, self.height)):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    nx, ny = pos[0] + dx, pos[1] + dy
                    if not self.in_bounds(nx, ny):
                        continue
                    tile = self.tiles[(nx, ny)]
                    if tile.l1 != TerrainType.TRENCH and tile.l1 != TerrainType.WATER:
                        return (nx, ny)
        return None

    def _bfs_passable(self, start: tuple[int, int]) -> set[tuple[int, int]]:
        """BFS from start on non-trench, non-water tiles. Returns reachable set."""
        visited: set[tuple[int, int]] = set()
        queue = [start]
        visited.add(start)

        while queue:
            cx, cy = queue.pop(0)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                npos = (nx, ny)
                if not self.in_bounds(nx, ny):
                    continue
                if npos in visited:
                    continue
                tile = self.tiles[npos]
                if tile.l1 == TerrainType.TRENCH or tile.l1 == TerrainType.WATER:
                    continue
                visited.add(npos)
                queue.append(npos)

        return visited

    def _most_common_neighbor_terrain(self, pos: tuple[int, int]) -> TerrainType:
        """Find the most common non-trench, non-water terrain among neighbors."""
        counts: dict[TerrainType, int] = {}
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = pos[0] + dx, pos[1] + dy
            if not self.in_bounds(nx, ny):
                continue
            tile = self.tiles[(nx, ny)]
            if tile.l1 != TerrainType.TRENCH and tile.l1 != TerrainType.WATER:
                counts[tile.l1] = counts.get(tile.l1, 0) + 1
        if counts:
            return max(counts, key=counts.get)
        return TerrainType.FLAT

    def _place_ore_veins(self):
        """Place ore veins with proper core-shell structure:
        metal ore in the inner core, stone in the outer shell.
        
        Key rules:
        1. Metal ore is placed FIRST and NEVER overwritten by stone
        2. Stone shell is placed SECOND, only on empty/vegetation tiles
        3. Stone shell has random gaps (~25%) for exposed ore (外露)
        4. Both small and large veins follow the same core-shell pattern
        
        Uses Euclidean distance + random perturbation for organic shapes."""
        rng = random.Random(self.seed + 5000)

        ore_config = [
            # (cover_type, min_veins, max_veins, min_radius, max_radius, allowed_zones)
            ("ore_copper", 20, 35, 1.5, 5.0, ["T1", "T2", "T3", "T4"]),
            ("ore_iron", 15, 25, 1.5, 5.0, ["T2", "T3", "T4"]),
            ("ore_uranium", 8, 15, 1.2, 3.5, ["T3", "T4"]),
            ("ore_gold", 5, 10, 1.2, 3.5, ["T3", "T4"]),
        ]

        for ore_id, min_v, max_v, min_r, max_r, allowed_zones in ore_config:
            num_veins = rng.randint(min_v, max_v)
            cover = CoverType(ore_id)
            ore_compat = COVER_L1_COMPAT.get(ore_id, [])
            stone_compat = COVER_L1_COMPAT.get("ore_stone", [])

            for _ in range(num_veins):
                placed = False
                for _attempt in range(80):
                    vy = rng.randint(0, self.height - 1)
                    zone = get_zone(vy, self.height)
                    if zone not in allowed_zones:
                        continue
                    vx = rng.randint(0, self.width - 1)

                    tile = self.tiles.get((vx, vy))
                    if not tile or tile.l1 not in ore_compat:
                        continue
                    if tile.l1 == TerrainType.WATER:
                        continue

                    # Random vein radius — can be small or large
                    vein_radius = rng.uniform(min_r, max_r)
                    core_radius = vein_radius * 0.55  # Metal core is 55% of total
                    ir = int(math.ceil(vein_radius)) + 1

                    # Collect positions for metal core and stone shell
                    metal_positions = []
                    stone_positions = []

                    for dx in range(-ir, ir + 1):
                        for dy in range(-ir, ir + 1):
                            nx, ny = vx + dx, vy + dy
                            if not self.in_bounds(nx, ny):
                                continue
                            ntile = self.tiles[(nx, ny)]
                            if ntile.l1 == TerrainType.WATER:
                                continue

                            dist = math.sqrt(dx * dx + dy * dy)
                            perturbed_dist = dist + rng.uniform(-0.5, 0.5)

                            if perturbed_dist <= core_radius:
                                # Inner core: metal ore
                                if ntile.l1 in ore_compat:
                                    metal_positions.append((nx, ny))
                            elif perturbed_dist <= vein_radius:
                                # Outer shell: stone with gaps for 外露
                                if ntile.l1 in stone_compat:
                                    if rng.random() < 0.75:  # 75% = some gaps
                                        stone_positions.append((nx, ny))

                    # PASS 1: Place metal ore (NEVER overwrites existing metal)
                    for nx, ny in metal_positions:
                        ntile = self.tiles[(nx, ny)]
                        # Don't overwrite existing metal ore (any non-stone ore)
                        if (ntile.l2 is not None
                                and ntile.l2.value.startswith("ore_")
                                and ntile.l2 != CoverType.ORE_STONE):
                            continue
                        ntile.l2 = cover
                        _, lo, hi = COVER_YIELDS[ore_id]
                        ntile.l2_remaining = rng.randint(lo, hi) if hi > lo else lo

                    # PASS 2: Place stone shell (NEVER overwrites any metal ore)
                    for nx, ny in stone_positions:
                        ntile = self.tiles[(nx, ny)]
                        # Don't overwrite any metal ore
                        if (ntile.l2 is not None
                                and ntile.l2.value.startswith("ore_")
                                and ntile.l2 != CoverType.ORE_STONE):
                            continue
                        ntile.l2 = CoverType.ORE_STONE
                        _, lo_s, hi_s = COVER_YIELDS["ore_stone"]
                        ntile.l2_remaining = rng.randint(lo_s, hi_s) if hi_s > lo_s else lo_s

                    placed = True
                    break

    def _place_vegetation(self, tile: Tile, x: int, y: int):
        """Place vegetation and organic resources on tiles without ore.
        Uses pre-computed cover noise for consistent placement."""
        zone = get_zone(y, self.height)
        cover_noise = self._cover_noise.get((x, y), _octave_noise(x, y, self.seed + 3000, 0.015, 4))
        cover = self._pick_cover(cover_noise, zone, tile.l1)
        if cover:
            tile.l2 = cover
            if cover in COVER_YIELDS:
                _, lo, hi = COVER_YIELDS[cover]
                tile.l2_remaining = random.randint(lo, hi) if hi > lo else lo
            else:
                tile.l2_remaining = 0

    def _pick_terrain(self, noise_val: float, weights: dict) -> TerrainType:
        """Pick terrain type based on noise value and blended weights.
        Uses weighted probability mapping with noise as selector."""
        # Normalize weights (they should sum to ~1.0 already, but ensure it)
        total = sum(weights.values())
        if total <= 0:
            return TerrainType.FLAT
        
        # Scale noise to [0, total) and walk through cumulative weights
        scaled = noise_val * total
        cumulative = 0.0
        for terrain_str, weight in weights.items():
            cumulative += weight
            if scaled <= cumulative:
                return TerrainType(terrain_str)
        return TerrainType.FLAT

    def _pick_cover(self, noise_val: float, zone: str, l1: TerrainType) -> Optional[CoverType]:
        """Pick cover type based on noise value and zone weights.
        Only considers covers compatible with the tile's L1 terrain,
        skipping incompatible ones so they don't waste noise budget."""
        covers = COVER_WEIGHTS.get(zone, {})
        cumulative = 0.0
        for cover_str, weight in covers.items():
            compat = COVER_L1_COMPAT.get(cover_str, [])
            if l1 not in compat:
                continue  # Skip incompatible covers entirely
            cumulative += weight
            if noise_val <= cumulative:
                return CoverType(cover_str)
        return None

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        return self.tiles.get((x, y))

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_passable(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if not tile:
            return False
        if tile.l1 == TerrainType.WATER:
            return False
        if tile.l3:
            return False  # Simplified: all buildings block
        return True

    def is_ore(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if not tile or not tile.l2:
            return False
        return tile.l2.value.startswith("ore_")

    def is_vegetation(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if not tile or not tile.l2:
            return False
        return tile.l2.value.startswith("veg_")

    # ─── Enclosure Detection ──────────────────────────────────────

    def _is_wall_or_door(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if not tile or not tile.l3:
            return False
        if self._buildings_ref:
            bldg = self._buildings_ref.get(tile.l3)
            if bldg and bldg.building_type in ("wall", "door"):
                return True
        return tile.l3.startswith("wall_") or tile.l3.startswith("door_")

    def check_enclosure_at(self, x: int, y: int) -> Optional[str]:
        start = (x, y)
        visited = set()
        queue = [start]

        while queue:
            cx, cy = queue.pop(0)
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))

            if len(visited) > ENCLOSURE_MAX_TILES:
                return None

            tile = self.get_tile(cx, cy)
            if not tile:
                return None

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if not self.in_bounds(nx, ny):
                    return None
                if self._is_wall_or_door(nx, ny):
                    continue
                if (nx, ny) in visited:
                    continue
                queue.append((nx, ny))

        if not visited:
            return None

        enc_id = f"enc_{self._next_enclosure_id}"
        self._next_enclosure_id += 1
        self.enclosures[enc_id] = visited

        for pos in visited:
            self._enclosure_cache[pos] = enc_id

        return enc_id

    def is_in_enclosure(self, x: int, y: int) -> bool:
        pos = (x, y)
        if pos in self._enclosure_cache:
            return self._enclosure_cache[pos] is not None
        enc_id = self.check_enclosure_at(x, y)
        if enc_id:
            return True
        self._enclosure_cache[pos] = None
        return False

    def get_enclosure_tiles(self, x: int, y: int) -> Optional[set[tuple[int, int]]]:
        pos = (x, y)
        enc_id = self._enclosure_cache.get(pos)
        if enc_id and enc_id in self.enclosures:
            return self.enclosures[enc_id]
        enc_id = self.check_enclosure_at(x, y)
        if enc_id:
            return self.enclosures[enc_id]
        return None

    def invalidate_enclosures_near(self, x: int, y: int):
        to_remove = []
        for enc_id, tiles in self.enclosures.items():
            for tx, ty in tiles:
                if abs(tx - x) <= 8 and abs(ty - y) <= 8:
                    to_remove.append(enc_id)
                    break
        for enc_id in to_remove:
            tiles = self.enclosures.pop(enc_id, None)
            if tiles:
                for pos in tiles:
                    self._enclosure_cache.pop(pos, None)

    # ─── Wood Renewal ─────────────────────────────────────────────

    def try_renew_wood(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if not tile or tile.l2 is not None:
            return False
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if abs(dx) + abs(dy) > 3:
                    continue
                nt = self.get_tile(x + dx, y + dy)
                if nt and nt.l2 and nt.l2.value.startswith("veg_"):
                    tile.l2 = nt.l2
                    _, lo, hi = COVER_YIELDS.get(nt.l2.value, ("wood", 1, 1))
                    tile.l2_remaining = random.randint(lo, hi) if hi > lo else lo
                    return True
        return False


# ─── Day/Night Cycle ──────────────────────────────────────────────

class DayNightCycle:
    def __init__(self):
        self.tick_in_cycle = 0

    def advance(self) -> DayPhase:
        phase = self.current_phase
        self.tick_in_cycle = (self.tick_in_cycle + 1) % DAY_CYCLE_TICKS
        return phase

    @property
    def current_phase(self) -> DayPhase:
        t = self.tick_in_cycle
        if t < DAY_TICKS:
            return DayPhase.DAY
        elif t < DAY_TICKS + DUSK_TICKS:
            return DayPhase.DUSK
        elif t < DAY_TICKS + DUSK_TICKS + NIGHT_TICKS:
            return DayPhase.NIGHT
        else:
            return DayPhase.DAWN

    @property
    def ticks_until_night(self) -> int:
        t = self.tick_in_cycle
        if t < DAY_TICKS:
            return DAY_TICKS - t
        elif t < DAY_TICKS + DUSK_TICKS:
            return 0
        else:
            remaining = DAY_CYCLE_TICKS - t
            return remaining + DAY_TICKS if remaining > 0 else 0

    def to_dict(self) -> dict:
        return {
            "day_phase": self.current_phase.value,
            "ticks_until_night": self.ticks_until_night,
            "tick_in_cycle": self.tick_in_cycle,
        }


# ─── Weather System ──────────────────────────────────────────────

class WeatherSystem:
    def __init__(self):
        self.current = WeatherType.QUIET
        self.storm_ticks_remaining = 0
        self.ticks_until_next_storm = random.randint(300, 600)

    def advance(self) -> tuple[WeatherType, list[str]]:
        events = []

        if self.current == WeatherType.RADIATION_STORM:
            self.storm_ticks_remaining -= 1
            if self.storm_ticks_remaining <= 0:
                self.current = WeatherType.QUIET
                self.ticks_until_next_storm = random.randint(300, 600)
                events.append("Radiation storm has dissipated")
        else:
            self.ticks_until_next_storm -= 1
            if self.ticks_until_next_storm <= 5 and self.ticks_until_next_storm > 0:
                events.append(f"Atmospheric radiation rising, storm expected in {self.ticks_until_next_storm} ticks")
            elif self.ticks_until_next_storm <= 0:
                self.current = WeatherType.RADIATION_STORM
                self.storm_ticks_remaining = 20
                events.append("Radiation storm has begun!")

        return self.current, events

    def to_dict(self) -> dict:
        return {
            "weather": self.current.value,
            "storm_ticks_remaining": self.storm_ticks_remaining,
        }

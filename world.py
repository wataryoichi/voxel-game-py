"""Voxel world with chunk-based terrain generation and infinite loading."""

import math
import random

CHUNK_SIZE = 16
MAX_HEIGHT = 64

# Block types
AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
WOOD = 4
LEAVES = 5
WATER = 6
SAND = 7

BLOCK_NAMES = {
    GRASS: 'Grass', DIRT: 'Dirt', STONE: 'Stone', WOOD: 'Wood',
    LEAVES: 'Leaves', WATER: 'Water', SAND: 'Sand',
}

# Base color + top/side variation for pseudo-textures
BLOCK_COLORS = {
    GRASS: {'top': (0.30, 0.75, 0.18), 'side': (0.35, 0.55, 0.20), 'bottom': (0.55, 0.36, 0.20)},
    DIRT:  {'top': (0.55, 0.36, 0.20), 'side': (0.50, 0.33, 0.18), 'bottom': (0.45, 0.30, 0.16)},
    STONE: {'top': (0.55, 0.55, 0.55), 'side': (0.48, 0.48, 0.48), 'bottom': (0.42, 0.42, 0.42)},
    WOOD:  {'top': (0.50, 0.35, 0.15), 'side': (0.60, 0.40, 0.20), 'bottom': (0.50, 0.35, 0.15)},
    LEAVES:{'top': (0.15, 0.60, 0.10), 'side': (0.12, 0.50, 0.08), 'bottom': (0.10, 0.45, 0.07)},
    WATER: {'top': (0.20, 0.40, 0.80), 'side': (0.15, 0.35, 0.75), 'bottom': (0.10, 0.30, 0.70)},
    SAND:  {'top': (0.85, 0.80, 0.55), 'side': (0.80, 0.75, 0.50), 'bottom': (0.75, 0.70, 0.45)},
}

TRANSPARENT_BLOCKS = {AIR, WATER, LEAVES}
WATER_LEVEL = 10


class Chunk:
    """A 16x64x16 column of blocks."""

    def __init__(self, cx: int, cz: int, seed: int):
        self.cx = cx
        self.cz = cz
        self.blocks = {}  # (lx, y, lz) -> block_type
        self.dirty = True
        self._generate(seed)

    def _generate(self, seed: int):
        rng = random.Random(seed ^ (self.cx * 73856093) ^ (self.cz * 19349663))
        for lx in range(CHUNK_SIZE):
            for lz in range(CHUNK_SIZE):
                wx = self.cx * CHUNK_SIZE + lx
                wz = self.cz * CHUNK_SIZE + lz
                h = self._heightmap(wx, wz, seed)

                for y in range(max(h, WATER_LEVEL + 1)):
                    if y < h:
                        if y < h - 4:
                            self.blocks[(lx, y, lz)] = STONE
                        elif y < h - 1:
                            self.blocks[(lx, y, lz)] = DIRT
                        else:
                            # Beach sand near water level
                            if h <= WATER_LEVEL + 2:
                                self.blocks[(lx, y, lz)] = SAND
                            else:
                                self.blocks[(lx, y, lz)] = GRASS
                    elif y <= WATER_LEVEL:
                        self.blocks[(lx, y, lz)] = WATER

                # Occasional tree on grass (not in water)
                if h > WATER_LEVEL + 2 and rng.random() < 0.008:
                    self._place_tree(lx, h, lz, rng)

    def _heightmap(self, wx: float, wz: float, seed: int) -> int:
        """Simple multi-octave value noise heightmap."""
        val = 0.0
        amp = 1.0
        freq = 0.02
        for _ in range(4):
            val += self._noise2d(wx * freq, wz * freq, seed) * amp
            amp *= 0.5
            freq *= 2.0
        h = int(12 + val * 10)
        return max(1, min(h, MAX_HEIGHT - 10))

    @staticmethod
    def _noise2d(x: float, z: float, seed: int) -> float:
        """Hash-based pseudo-noise in [-1, 1]."""
        ix = int(math.floor(x))
        iz = int(math.floor(z))
        fx = x - ix
        fz = z - iz

        def _hash(a: int, b: int) -> float:
            n = (a * 374761393 + b * 668265263 + seed) & 0xFFFFFFFF
            n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
            return (n / 2147483648.0) - 1.0

        v00 = _hash(ix, iz)
        v10 = _hash(ix + 1, iz)
        v01 = _hash(ix, iz + 1)
        v11 = _hash(ix + 1, iz + 1)

        sx = fx * fx * (3 - 2 * fx)
        sz = fz * fz * (3 - 2 * fz)

        a = v00 + sx * (v10 - v00)
        b = v01 + sx * (v11 - v01)
        return a + sz * (b - a)

    def _place_tree(self, lx: int, base_y: int, lz: int, rng):
        trunk_h = rng.randint(4, 6)
        for dy in range(trunk_h):
            self.blocks[(lx, base_y + dy, lz)] = WOOD
        top = base_y + trunk_h
        for dy in range(-1, 2):
            for dlx in range(-2, 3):
                for dlz in range(-2, 3):
                    nlx, nlz = lx + dlx, lz + dlz
                    if 0 <= nlx < CHUNK_SIZE and 0 <= nlz < CHUNK_SIZE:
                        if (nlx, top + dy, nlz) not in self.blocks:
                            dist = abs(dlx) + abs(dlz) + max(0, dy)
                            if dist <= 3:
                                self.blocks[(nlx, top + dy, nlz)] = LEAVES

    def get(self, lx: int, y: int, lz: int) -> int:
        return self.blocks.get((lx, y, lz), AIR)

    def set(self, lx: int, y: int, lz: int, block: int):
        if block == AIR:
            self.blocks.pop((lx, y, lz), None)
        else:
            self.blocks[(lx, y, lz)] = block
        self.dirty = True


class World:
    """Collection of chunks with infinite dynamic loading."""

    def __init__(self, chunk_radius: int = 4, seed: int = 42):
        self.seed = seed
        self.chunks: dict[tuple[int, int], Chunk] = {}
        self.chunk_radius = chunk_radius
        self.max_chunks = (chunk_radius * 2 + 3) ** 2
        self._modified_chunks: dict[tuple[int, int], Chunk] = {}  # edits survive unload
        self._on_chunk_unload = None  # callback for renderer cleanup
        # Pre-generate around origin
        for cx in range(-chunk_radius, chunk_radius + 1):
            for cz in range(-chunk_radius, chunk_radius + 1):
                self.chunks[(cx, cz)] = Chunk(cx, cz, seed)

    def _ensure_chunk(self, cx: int, cz: int) -> Chunk:
        if (cx, cz) not in self.chunks:
            # Restore previously modified chunk or generate fresh
            if (cx, cz) in self._modified_chunks:
                chunk = self._modified_chunks[(cx, cz)]
                chunk.dirty = True
            else:
                chunk = Chunk(cx, cz, self.seed)
            self.chunks[(cx, cz)] = chunk
        return self.chunks[(cx, cz)]

    def get_block(self, wx: int, wy: int, wz: int) -> int:
        cx, lx = divmod(wx, CHUNK_SIZE)
        cz, lz = divmod(wz, CHUNK_SIZE)
        chunk = self.chunks.get((cx, cz))
        if chunk is None:
            return AIR
        return chunk.get(lx, wy, lz)

    def set_block(self, wx: int, wy: int, wz: int, block: int):
        cx, lx = divmod(wx, CHUNK_SIZE)
        cz, lz = divmod(wz, CHUNK_SIZE)
        chunk = self._ensure_chunk(cx, cz)
        chunk.set(lx, wy, lz, block)
        # Mark chunk as player-modified so edits survive unload
        self._modified_chunks[(cx, cz)] = chunk

        # Dirty neighboring chunks when editing a border block
        if lx == 0 and (cx - 1, cz) in self.chunks:
            self.chunks[(cx - 1, cz)].dirty = True
        if lx == CHUNK_SIZE - 1 and (cx + 1, cz) in self.chunks:
            self.chunks[(cx + 1, cz)].dirty = True
        if lz == 0 and (cx, cz - 1) in self.chunks:
            self.chunks[(cx, cz - 1)].dirty = True
        if lz == CHUNK_SIZE - 1 and (cx, cz + 1) in self.chunks:
            self.chunks[(cx, cz + 1)].dirty = True

    def get_height(self, wx: int, wz: int) -> int:
        """Return the highest solid block Y at (wx, wz)."""
        cx = wx // CHUNK_SIZE
        cz = wz // CHUNK_SIZE
        lx = wx % CHUNK_SIZE
        lz = wz % CHUNK_SIZE
        chunk = self._ensure_chunk(cx, cz)
        max_y = 0
        for (bx, by, bz), bt in chunk.blocks.items():
            if bx == lx and bz == lz and bt not in TRANSPARENT_BLOCKS and by >= max_y:
                max_y = by + 1
        return max_y

    def is_solid(self, wx: int, wy: int, wz: int) -> bool:
        block = self.get_block(wx, wy, wz)
        return block != AIR and block != WATER

    def update_chunks_around(self, px: float, pz: float):
        """Load chunks around player, unload distant ones."""
        cx = int(math.floor(px)) // CHUNK_SIZE
        cz = int(math.floor(pz)) // CHUNK_SIZE

        # Load missing chunks in range
        for dx in range(-self.chunk_radius, self.chunk_radius + 1):
            for dz in range(-self.chunk_radius, self.chunk_radius + 1):
                self._ensure_chunk(cx + dx, cz + dz)

        # Unload far chunks to cap memory
        if len(self.chunks) > self.max_chunks:
            to_remove = []
            for key in self.chunks:
                dist = abs(key[0] - cx) + abs(key[1] - cz)
                if dist > self.chunk_radius + 2:
                    to_remove.append(key)
            for key in to_remove:
                del self.chunks[key]
                if self._on_chunk_unload:
                    self._on_chunk_unload(key)

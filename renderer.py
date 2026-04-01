"""OpenGL chunk renderer with display-list caching, face culling, and per-face colors."""

import math
from OpenGL.GL import *

from world import (CHUNK_SIZE, AIR, BLOCK_COLORS, TRANSPARENT_BLOCKS,
                   WATER, LEAVES)

# Face definitions: (vertices) for a unit cube at origin
# Each face is 4 vertices in CCW winding order viewed from outside
_FACES = {
    'top':    [(0,1,0),(1,1,0),(1,1,1),(0,1,1)],
    'bottom': [(0,0,1),(1,0,1),(1,0,0),(0,0,0)],
    'front':  [(0,0,1),(0,1,1),(1,1,1),(1,0,1)],
    'back':   [(1,0,0),(1,1,0),(0,1,0),(0,0,0)],
    'right':  [(1,0,1),(1,1,1),(1,1,0),(1,0,0)],
    'left':   [(0,0,0),(0,1,0),(0,1,1),(0,0,1)],
}

# Ambient shading per face direction
_FACE_SHADE = {
    'top': 1.0, 'bottom': 0.4,
    'front': 0.8, 'back': 0.6,
    'right': 0.7, 'left': 0.7,
}

# Neighbor offset per face
_NEIGHBOR = {
    'top': (0, 1, 0), 'bottom': (0, -1, 0),
    'front': (0, 0, 1), 'back': (0, 0, -1),
    'right': (1, 0, 0), 'left': (-1, 0, 0),
}

# Which color key to use per face
_FACE_COLOR_KEY = {
    'top': 'top', 'bottom': 'bottom',
    'front': 'side', 'back': 'side',
    'right': 'side', 'left': 'side',
}


class Renderer:
    def __init__(self, world):
        self.world = world
        self._display_lists: dict[tuple[int, int], int] = {}
        self._water_lists: dict[tuple[int, int], int] = {}
        # Register cleanup callback for chunk unloading
        world._on_chunk_unload = self._on_chunk_unload

    def _on_chunk_unload(self, key):
        """Release GL display lists when a chunk is evicted."""
        if key in self._display_lists:
            glDeleteLists(self._display_lists.pop(key), 1)
        if key in self._water_lists:
            glDeleteLists(self._water_lists.pop(key), 1)

    def draw(self, player, brightness=1.0, fps=0):
        self._brightness = brightness
        self._fps = fps

        # Apply day/night brightness via color scaling
        # GL_MODULATE with a texture would be ideal, but we use glColor scaling
        # by enabling GL_COLOR_MATERIAL and scaling via GL lighting ambient
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        b = brightness
        glLightfv(GL_LIGHT0, GL_AMBIENT, [b, b, b, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [b * 0.3, b * 0.3, b * 0.3, 1.0])
        glLightfv(GL_LIGHT0, GL_POSITION, [0.5, 1.0, 0.3, 0.0])

        # Opaque pass
        for (cx, cz), chunk in self.world.chunks.items():
            px = cx * CHUNK_SIZE + CHUNK_SIZE / 2
            pz = cz * CHUNK_SIZE + CHUNK_SIZE / 2
            dist = math.sqrt((px - player.x) ** 2 + (pz - player.z) ** 2)
            if dist > (self.world.chunk_radius + 1) * CHUNK_SIZE:
                continue

            if chunk.dirty or (cx, cz) not in self._display_lists:
                self._build_chunk(cx, cz, chunk)
                chunk.dirty = False

            glCallList(self._display_lists[(cx, cz)])

        # Transparent pass (water/leaves) — sorted back-to-front
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)

        sorted_transparent = []
        for (cx, cz), dl in list(self._water_lists.items()):
            if (cx, cz) not in self.world.chunks:
                continue
            cpx = cx * CHUNK_SIZE + CHUNK_SIZE / 2
            cpz = cz * CHUNK_SIZE + CHUNK_SIZE / 2
            dist_sq = (cpx - player.x) ** 2 + (cpz - player.z) ** 2
            max_dist = (self.world.chunk_radius + 1) * CHUNK_SIZE
            if dist_sq > max_dist * max_dist:
                continue
            sorted_transparent.append((dist_sq, dl))

        sorted_transparent.sort(key=lambda x: x[0], reverse=True)
        for _, dl in sorted_transparent:
            glCallList(dl)

        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)

        # Disable lighting for HUD
        glDisable(GL_LIGHTING)

        self._draw_crosshair()
        self._draw_hud(player)
        self._draw_fps()

    def _build_chunk(self, cx: int, cz: int, chunk):
        # Clean up old lists
        if (cx, cz) in self._display_lists:
            glDeleteLists(self._display_lists[(cx, cz)], 1)
        if (cx, cz) in self._water_lists:
            glDeleteLists(self._water_lists[(cx, cz)], 1)

        ox = cx * CHUNK_SIZE
        oz = cz * CHUNK_SIZE

        # Opaque list
        dl = glGenLists(1)
        glNewList(dl, GL_COMPILE)
        glBegin(GL_QUADS)

        for (lx, y, lz), block in chunk.blocks.items():
            if block == AIR or block in TRANSPARENT_BLOCKS:
                continue
            self._emit_block(ox + lx, y, oz + lz, block)

        glEnd()
        glEndList()
        self._display_lists[(cx, cz)] = dl

        # Transparent list
        wl = glGenLists(1)
        glNewList(wl, GL_COMPILE)
        glBegin(GL_QUADS)

        for (lx, y, lz), block in chunk.blocks.items():
            if block not in TRANSPARENT_BLOCKS or block == AIR:
                continue
            self._emit_block(ox + lx, y, oz + lz, block, transparent=True)

        glEnd()
        glEndList()
        self._water_lists[(cx, cz)] = wl

    def _emit_block(self, wx, y, wz, block, transparent=False):
        colors = BLOCK_COLORS.get(block, {'top': (1, 0, 1), 'side': (1, 0, 1), 'bottom': (1, 0, 1)})
        alpha = 0.6 if block == WATER else (0.85 if block == LEAVES else 1.0)

        for face_name, verts in _FACES.items():
            ndx, ndy, ndz = _NEIGHBOR[face_name]
            neighbor = self.world.get_block(wx + ndx, y + ndy, wz + ndz)

            if transparent:
                if neighbor == block:
                    continue
            else:
                if neighbor not in TRANSPARENT_BLOCKS:
                    continue

            color_key = _FACE_COLOR_KEY[face_name]
            shade = _FACE_SHADE[face_name]
            r, g, b = colors[color_key]
            r *= shade
            g *= shade
            b *= shade

            if alpha < 1.0:
                glColor4f(r, g, b, alpha)
            else:
                glColor3f(r, g, b)

            for vx, vy, vz in verts:
                glVertex3f(wx + vx, y + vy, wz + vz)

    def _draw_crosshair(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(-1, 1, -1, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)
        glLineWidth(2.0)
        glColor3f(1.0, 1.0, 1.0)
        size = 0.02
        glBegin(GL_LINES)
        glVertex2f(-size, 0)
        glVertex2f(size, 0)
        glVertex2f(0, -size)
        glVertex2f(0, size)
        glEnd()
        glEnable(GL_DEPTH_TEST)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def _draw_hud(self, player):
        """Draw hotbar at bottom center."""
        from world import BLOCK_NAMES
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, 1, 0, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)

        block_types = [1, 2, 3, 4, 5, 7]  # placeable blocks
        slot_size = 0.045
        gap = 0.008
        total_w = len(block_types) * slot_size + (len(block_types) - 1) * gap
        x_start = 0.5 - total_w / 2
        y_base = 0.02

        # Background bar
        glColor4f(0.0, 0.0, 0.0, 0.4)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glBegin(GL_QUADS)
        glVertex2f(x_start - 0.01, y_base - 0.01)
        glVertex2f(x_start + total_w + 0.01, y_base - 0.01)
        glVertex2f(x_start + total_w + 0.01, y_base + slot_size + 0.01)
        glVertex2f(x_start - 0.01, y_base + slot_size + 0.01)
        glEnd()
        glDisable(GL_BLEND)

        for i, bt in enumerate(block_types):
            x = x_start + i * (slot_size + gap)
            colors = BLOCK_COLORS.get(bt, {'top': (1, 0, 1)})
            color = colors.get('top', (1, 0, 1))

            # Selection highlight
            if bt == player.selected_block:
                glColor3f(1.0, 1.0, 1.0)
                glLineWidth(2.0)
                glBegin(GL_LINE_LOOP)
                glVertex2f(x - 0.004, y_base - 0.004)
                glVertex2f(x + slot_size + 0.004, y_base - 0.004)
                glVertex2f(x + slot_size + 0.004, y_base + slot_size + 0.004)
                glVertex2f(x - 0.004, y_base + slot_size + 0.004)
                glEnd()

            glColor3f(*color)
            glBegin(GL_QUADS)
            glVertex2f(x, y_base)
            glVertex2f(x + slot_size, y_base)
            glVertex2f(x + slot_size, y_base + slot_size)
            glVertex2f(x, y_base + slot_size)
            glEnd()

        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def _draw_fps(self):
        """Draw FPS bar indicator at top-right (no font dependency)."""
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, 1, 0, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)

        # FPS bar: green=60+, yellow=30-59, red=<30
        fps = self._fps
        bar_w = min(fps / 60.0, 1.0) * 0.15
        if fps >= 50:
            glColor3f(0.2, 0.8, 0.2)
        elif fps >= 30:
            glColor3f(0.8, 0.8, 0.2)
        else:
            glColor3f(0.8, 0.2, 0.2)

        x, y = 0.83, 0.96
        glBegin(GL_QUADS)
        glVertex2f(x, y)
        glVertex2f(x + bar_w, y)
        glVertex2f(x + bar_w, y + 0.02)
        glVertex2f(x, y + 0.02)
        glEnd()

        # Border
        glColor3f(1, 1, 1)
        glBegin(GL_LINE_LOOP)
        glVertex2f(x, y)
        glVertex2f(x + 0.15, y)
        glVertex2f(x + 0.15, y + 0.02)
        glVertex2f(x, y + 0.02)
        glEnd()

        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

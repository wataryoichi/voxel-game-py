"""OpenGL chunk renderer with display-list caching and face culling."""

import math
from OpenGL.GL import *

from world import CHUNK_SIZE, MAX_HEIGHT, AIR, BLOCK_COLORS

# Face definitions: (normal, vertices) for a unit cube at origin
# Each face is 4 vertices in CCW winding order viewed from outside
_FACES = {
    'top':    ((0, 1, 0),  [(0,1,0),(1,1,0),(1,1,1),(0,1,1)]),
    'bottom': ((0,-1,0),   [(0,0,1),(1,0,1),(1,0,0),(0,0,0)]),
    'front':  ((0, 0, 1),  [(0,0,1),(0,1,1),(1,1,1),(1,0,1)]),
    'back':   ((0, 0,-1),  [(1,0,0),(1,1,0),(0,1,0),(0,0,0)]),
    'right':  ((1, 0, 0),  [(1,0,1),(1,1,1),(1,1,0),(1,0,0)]),
    'left':   ((-1,0, 0),  [(0,0,0),(0,1,0),(0,1,1),(0,0,1)]),
}

# Ambient occlusion-ish shading per face
_FACE_SHADE = {
    'top': 1.0,
    'bottom': 0.4,
    'front': 0.8,
    'back': 0.6,
    'right': 0.7,
    'left': 0.7,
}

# Neighbor offsets for each face
_NEIGHBOR = {
    'top':    (0, 1, 0),
    'bottom': (0,-1, 0),
    'front':  (0, 0, 1),
    'back':   (0, 0,-1),
    'right':  (1, 0, 0),
    'left':   (-1,0, 0),
}


class Renderer:
    def __init__(self, world):
        self.world = world
        self._display_lists: dict[tuple[int, int], int] = {}

    def draw(self, player):
        for (cx, cz), chunk in self.world.chunks.items():
            # Simple distance cull
            px = cx * CHUNK_SIZE + CHUNK_SIZE / 2
            pz = cz * CHUNK_SIZE + CHUNK_SIZE / 2
            dist = math.sqrt((px - player.x) ** 2 + (pz - player.z) ** 2)
            if dist > (self.world.chunk_radius + 1) * CHUNK_SIZE:
                continue

            if chunk.dirty or (cx, cz) not in self._display_lists:
                self._build_chunk(cx, cz, chunk)
                chunk.dirty = False

            glCallList(self._display_lists[(cx, cz)])

        # Draw crosshair
        self._draw_crosshair()

        # Draw HUD (selected block)
        self._draw_hud(player)

    def _build_chunk(self, cx: int, cz: int, chunk):
        if (cx, cz) in self._display_lists:
            glDeleteLists(self._display_lists[(cx, cz)], 1)

        dl = glGenLists(1)
        glNewList(dl, GL_COMPILE)
        glBegin(GL_QUADS)

        ox = cx * CHUNK_SIZE
        oz = cz * CHUNK_SIZE

        for (lx, y, lz), block in chunk.blocks.items():
            if block == AIR:
                continue
            wx, wz = ox + lx, oz + lz
            base_color = BLOCK_COLORS.get(block, (1.0, 0.0, 1.0))

            for face_name, (normal, verts) in _FACES.items():
                ndx, ndy, ndz = _NEIGHBOR[face_name]
                if self.world.get_block(wx + ndx, y + ndy, wz + ndz) != AIR:
                    continue

                shade = _FACE_SHADE[face_name]
                r = base_color[0] * shade
                g = base_color[1] * shade
                b = base_color[2] * shade
                glColor3f(r, g, b)

                for vx, vy, vz in verts:
                    glVertex3f(wx + vx, y + vy, wz + vz)

        glEnd()
        glEndList()
        self._display_lists[(cx, cz)] = dl

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
        """Draw selected block indicator in bottom-left."""
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, 1, 0, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)

        block_types = [1, 2, 3, 4]
        names = {1: 'Grass', 2: 'Dirt', 3: 'Stone', 4: 'Wood'}
        x_start = 0.02
        size = 0.04

        for i, bt in enumerate(block_types):
            x = x_start + i * (size + 0.01)
            y = 0.02
            color = BLOCK_COLORS.get(bt, (1, 0, 1))

            if bt == player.selected_block:
                glColor3f(1.0, 1.0, 1.0)
                glBegin(GL_LINE_LOOP)
                glVertex2f(x - 0.005, y - 0.005)
                glVertex2f(x + size + 0.005, y - 0.005)
                glVertex2f(x + size + 0.005, y + size + 0.005)
                glVertex2f(x - 0.005, y + size + 0.005)
                glEnd()

            glColor3f(*color)
            glBegin(GL_QUADS)
            glVertex2f(x, y)
            glVertex2f(x + size, y)
            glVertex2f(x + size, y + size)
            glVertex2f(x, y + size)
            glEnd()

        glEnable(GL_DEPTH_TEST)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

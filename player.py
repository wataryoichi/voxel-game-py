"""First-person player with WASD movement, mouse look, and simple physics."""

import math
from OpenGL.GL import *
from OpenGL.GLU import *

GRAVITY = -20.0
JUMP_VEL = 7.0
MOVE_SPEED = 5.0
MOUSE_SENS = 0.15
PLAYER_W = 0.3   # half-width for collision
PLAYER_H = 1.7   # full height
EYE_OFFSET = 1.5


class Player:
    def __init__(self, x=0.0, y=10.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z
        self.yaw = 0.0
        self.pitch = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.selected_block = 1  # GRASS
        self.eye_height = EYE_OFFSET

    def handle_mouse(self, rel):
        dx, dy = rel
        self.yaw = (self.yaw + dx * MOUSE_SENS) % 360
        self.pitch = max(-89.0, min(89.0, self.pitch - dy * MOUSE_SENS))

    def handle_keys(self, keys, dt: float):
        import pygame
        speed = MOVE_SPEED * dt
        rad = math.radians(self.yaw)
        sin_y = math.sin(rad)
        cos_y = math.cos(rad)

        dx, dz = 0.0, 0.0
        if keys[pygame.K_w]:
            dx -= sin_y * speed
            dz -= cos_y * speed
        if keys[pygame.K_s]:
            dx += sin_y * speed
            dz += cos_y * speed
        if keys[pygame.K_a]:
            dx -= cos_y * speed
            dz += sin_y * speed
        if keys[pygame.K_d]:
            dx += cos_y * speed
            dz -= sin_y * speed

        self._pending_dx = dx
        self._pending_dz = dz

        if keys[pygame.K_SPACE] and self.on_ground:
            self.vy = JUMP_VEL
            self.on_ground = False

    def apply_physics(self, world, dt: float):
        dx = getattr(self, '_pending_dx', 0.0)
        dz = getattr(self, '_pending_dz', 0.0)

        # Horizontal movement with collision
        new_x = self.x + dx
        if not self._collides(world, new_x, self.y, self.z):
            self.x = new_x

        new_z = self.z + dz
        if not self._collides(world, self.x, self.y, new_z):
            self.z = new_z

        # Gravity
        self.vy += GRAVITY * dt
        new_y = self.y + self.vy * dt

        if self.vy < 0:
            if self._collides(world, self.x, new_y, self.z):
                # Land — snap feet to top of the block we collided with
                self.y = math.floor(new_y) + 1.0 + 0.001
                self.vy = 0.0
                self.on_ground = True
            else:
                self.y = new_y
                self.on_ground = False
        else:
            if self._collides(world, self.x, new_y, self.z):
                self.vy = 0.0
            else:
                self.y = new_y
            self.on_ground = False

        # Update chunks around player
        world.update_chunks_around(self.x, self.z)

    def _collides(self, world, px, py, pz) -> bool:
        """AABB collision against world blocks."""
        min_bx = int(math.floor(px - PLAYER_W))
        max_bx = int(math.floor(px + PLAYER_W))
        min_by = int(math.floor(py))
        max_by = int(math.floor(py + PLAYER_H))
        min_bz = int(math.floor(pz - PLAYER_W))
        max_bz = int(math.floor(pz + PLAYER_W))

        for bx in range(min_bx, max_bx + 1):
            for by in range(min_by, max_by + 1):
                for bz in range(min_bz, max_bz + 1):
                    if world.is_solid(bx, by, bz):
                        return True
        return False

    def apply_camera(self):
        glRotatef(-self.pitch, 1, 0, 0)
        glRotatef(self.yaw, 0, 1, 0)
        glTranslatef(-self.x, -(self.y + self.eye_height), -self.z)

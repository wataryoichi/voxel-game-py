"""Minecraft-style voxel game — Pygame + OpenGL."""

import sys
import math
import time
import ctypes

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

from world import World
from player import Player
from renderer import Renderer

WINDOW_W, WINDOW_H = 960, 640
FPS = 60
FOV = 70.0
NEAR_CLIP = 0.1
FAR_CLIP = 200.0


def main():
    pygame.init()
    pygame.display.set_mode((WINDOW_W, WINDOW_H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Voxel Game")
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)
    glClearColor(0.53, 0.81, 0.92, 1.0)  # sky blue

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOV, WINDOW_W / WINDOW_H, NEAR_CLIP, FAR_CLIP)
    glMatrixMode(GL_MODELVIEW)

    world = World(chunk_radius=3, seed=42)
    player = Player(x=8.0, y=world.get_height(8, 8) + 2.0, z=8.0)
    renderer = Renderer(world)

    clock = pygame.time.Clock()
    prev_time = time.monotonic()

    while True:
        now = time.monotonic()
        dt = min(now - prev_time, 0.05)  # cap delta to avoid spiral
        prev_time = now

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key in (K_1, K_2, K_3, K_4):
                    player.selected_block = event.key - K_1 + 1
            elif event.type == MOUSEMOTION:
                player.handle_mouse(event.rel)
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1:
                    _ray_action(player, world, remove=True)
                elif event.button == 3:
                    _ray_action(player, world, remove=False)

        keys = pygame.key.get_pressed()
        player.handle_keys(keys, dt)
        player.apply_physics(world, dt)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        player.apply_camera()
        renderer.draw(player)

        pygame.display.flip()
        clock.tick(FPS)


def _ray_action(player, world, remove: bool):
    """Cast a ray from the player's eye and break/place a block."""
    reach = 6.0
    step = 0.05
    dx = -math.sin(math.radians(player.yaw)) * math.cos(math.radians(player.pitch))
    dy = math.sin(math.radians(player.pitch))
    dz = -math.cos(math.radians(player.yaw)) * math.cos(math.radians(player.pitch))

    px, py, pz = player.x, player.y + player.eye_height, player.z
    prev_bx, prev_by, prev_bz = None, None, None

    t = 0.0
    while t < reach:
        bx = int(math.floor(px + dx * t))
        by = int(math.floor(py + dy * t))
        bz = int(math.floor(pz + dz * t))

        if (bx, by, bz) != (prev_bx, prev_by, prev_bz):
            if world.get_block(bx, by, bz) != 0:
                if remove:
                    world.set_block(bx, by, bz, 0)
                elif prev_bx is not None:
                    world.set_block(prev_bx, prev_by, prev_bz, player.selected_block)
                return
            prev_bx, prev_by, prev_bz = bx, by, bz
        t += step


if __name__ == "__main__":
    main()

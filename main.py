"""Minecraft-style voxel game — Pygame + OpenGL."""

import sys
import math
import time

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
DAY_LENGTH = 120.0  # seconds per full day cycle


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Voxel Game")
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)

    # Fog setup
    glEnable(GL_FOG)
    glFogi(GL_FOG_MODE, GL_LINEAR)
    glFogf(GL_FOG_START, 40.0)
    glFogf(GL_FOG_END, 70.0)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOV, WINDOW_W / WINDOW_H, NEAR_CLIP, FAR_CLIP)
    glMatrixMode(GL_MODELVIEW)

    world = World(chunk_radius=4, seed=42)
    player = Player(x=8.0, y=world.get_height(8, 8) + 2.0, z=8.0)
    renderer = Renderer(world)

    clock = pygame.time.Clock()
    prev_time = time.monotonic()
    game_time = DAY_LENGTH * 0.25  # start at sunrise
    fps_timer = 0.0
    fps_display = 0

    while True:
        now = time.monotonic()
        dt = min(now - prev_time, 0.05)
        prev_time = now
        game_time += dt

        # FPS counter (update every 0.5s)
        fps_timer += dt
        if fps_timer >= 0.5:
            fps_display = int(clock.get_fps())
            fps_timer = 0.0

        # Day-night cycle
        day_phase = (game_time % DAY_LENGTH) / DAY_LENGTH  # 0..1
        sun_angle = day_phase * 2 * math.pi
        brightness = max(0.15, (math.sin(sun_angle) + 0.3) / 1.3)
        brightness = min(1.0, brightness)

        sky_r = 0.53 * brightness
        sky_g = 0.81 * brightness
        sky_b = 0.92 * brightness
        glClearColor(sky_r, sky_g, sky_b, 1.0)
        glFogfv(GL_FOG_COLOR, [sky_r, sky_g, sky_b, 1.0])

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key in (K_1, K_2, K_3, K_4, K_5, K_6):
                    block_map = {K_1: 1, K_2: 2, K_3: 3, K_4: 4, K_5: 5, K_6: 7}
                    player.selected_block = block_map.get(event.key, 1)
                elif event.key == K_e:
                    cycle = [1, 2, 3, 4, 5, 7]
                    idx = cycle.index(player.selected_block) if player.selected_block in cycle else 0
                    player.selected_block = cycle[(idx + 1) % len(cycle)]
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
        renderer.draw(player, brightness, fps_display)

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

# Voxel Game

A Minecraft-inspired voxel game built with Python, Pygame, and OpenGL.

## Requirements

- Python 3.10+
- macOS (tested on desktop)

## Setup

```bash
git clone https://github.com/wataryoichi/voxel-game-py.git
cd voxel-game-py
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controls

- WASD: Move
- Shift: Sprint
- Mouse: Look around
- Left click: Break block
- Right click: Place block
- 1-6: Select block type (grass, dirt, stone, wood, leaves, sand)
- E: Cycle through block types
- Space: Jump
- ESC: Quit

## Features

- Procedural terrain generation with noise-based heightmaps
- Infinite terrain (chunks load/unload dynamically)
- 7 block types with per-face coloring
- Water with transparency
- Tree generation with leaf blocks
- Beach/sand near water level
- Block place and break via raycasting
- Player edits persist across chunk unloads
- Simple physics (gravity, collision, jumping)
- Sprint mode (Shift)
- Day-night cycle (120s period) with dynamic sky color
- Distance fog
- FPS indicator bar (top-right)
- Hotbar HUD with selection indicator

#!/usr/bin/env python
"""
Complete diagnostic script for light leakage debugging.

This script:
1. Sets up a test scene with a wall and light source
2. Runs the lighting calculation
3. Performs comprehensive diagnostics
4. Reports exactly where light is leaking and why

Usage:
    python complete_light_diagnostic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add the uploads directory to path so we can import the modules
uploads_path = Path("/mnt/user-data/uploads")
if uploads_path.exists():
    sys.path.insert(0, str(uploads_path))

import numpy as np
from numpy.typing import NDArray

# Import the actual modules
try:
    from lights_dev import constants
    from lights_dev.dungeon_data import Dungeon
    from lights_dev.entities import LightSource
    from lights_dev.lighting import LightContext, Light
    from lights_dev.fov import compute_fov_all_octants
    print("✓ Successfully imported all modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nMake sure the following files are in /mnt/user-data/uploads:")
    print("  - constants.py")
    print("  - dungeon_data.py")
    print("  - entities.py")
    print("  - lighting.py (NEW corrected version)")
    print("  - fov.py")
    sys.exit(1)


def create_simple_test_scene() -> tuple[Dungeon, LightSource, int, int]:
    """
    Create a simple test scene:
    
    Layout (9x9):
    . . . . . . . . .
    . . . . . . . . .
    . . . . . . . . .
    . . . # # # . . .
    L . . # . # . . T
    . . . # # # . . .
    . . . . . . . . .
    . . . . . . . . .
    . . . . . . . . .
    
    Where:
    - L = Light source at (0, 4)
    - # = Wall room (3x3) at (3-5, 3-5) with door at (4, 4)
    - T = Target behind wall at (8, 4)
    """
    from utils.game_rng import GameRNG
    
    width, height = 9, 9
    dungeon = Dungeon(width, height)
    
    # Fill with floor
    dungeon.tiles[:, :] = constants.FLOOR_ID
    
    # Create a 3x3 walled room with a door
    for y in range(3, 6):
        for x in range(3, 6):
            dungeon.tiles[y, x] = constants.WALL_ID
    
    # Create door in the middle
    dungeon.tiles[4, 4] = constants.FLOOR_ID
    
    # Create light source on the left
    rng = GameRNG(seed=12345)
    light_source = LightSource(
        0,
        y=4,
        rng=rng,
        light_radius=15,
        light_level=5,
        flicker=False,
        base_color_rgb=constants.TORCH_COLOR_RGB,
        height=1.5,
    )
    
    # Target position is behind the wall
    target_x, target_y = 8, 4
    
    return dungeon, light_source, target_x, target_y


def print_dungeon_layout(dungeon: Dungeon, light_x: int, light_y: int, target_x: int, target_y: int) -> None:
    """Print ASCII representation of the dungeon."""
    print("\n" + "="*60)
    print("DUNGEON LAYOUT")
    print("="*60)
    
    for y in range(dungeon.height):
        row = []
        for x in range(dungeon.width):
            if (x, y) == (light_x, light_y):
                row.append('L')
            elif (x, y) == (target_x, target_y):
                row.append('T')
            elif dungeon.blocks_light(x, y):
                row.append('#')
            else:
                row.append('.')
        print(' '.join(row))
    
    print(f"\nL = Light source at ({light_x}, {light_y})")
    print(f"T = Target at ({target_x}, {target_y})")
    print(f"# = Opaque tile (wall)")
    print(f". = Transparent tile (floor)")
    print()


def check_blocks_light_implementation(dungeon: Dungeon) -> None:
    """Verify blocks_light() implementation."""
    print("="*60)
    print("PRE-CHECK: blocks_light() Implementation")
    print("="*60)
    
    # Check what tile types exist
    unique_tiles = np.unique(dungeon.tiles)
    print(f"Tile types present: {unique_tiles}")
    
    # Check if blocks_light returns True for each type
    print("\nblocks_light() behavior:")
    for tile_id in unique_tiles:
        # Find a cell with this tile
        y, x = np.argwhere(dungeon.tiles == tile_id)[0]
        blocks = dungeon.blocks_light(x, y)
        tile_name = "WALL" if tile_id == constants.WALL_ID else \
                   "PILLAR" if tile_id == constants.PILLAR_ID else \
                   "FLOOR" if tile_id == constants.FLOOR_ID else \
                   f"UNKNOWN({tile_id})"
        print(f"  {tile_name} (id={tile_id}): blocks={blocks}")
    
    # Check for pillars specifically
    has_pillars = np.any(dungeon.tiles == constants.PILLAR_ID)
    if has_pillars:
        pillar_coords = np.argwhere(dungeon.tiles == constants.PILLAR_ID)[0]
        py, px = pillar_coords
        blocks = dungeon.blocks_light(px, py)
        if not blocks:
            print(f"\n❌ BUG FOUND: Pillar at ({px},{py}) does NOT block light!")
            print("   This is likely your light leakage issue.")
        else:
            print(f"\n✓ Pillars correctly block light")
    
    print()


def check_transparency_array(
    opaque: NDArray[np.uint8],
    transparency: NDArray[np.float32],
) -> None:
    """Verify transparency array is constructed correctly."""
    print("="*60)
    print("DIAGNOSTIC 1: Transparency Array Construction")
    print("="*60)
    
    h, w = opaque.shape
    total_cells = h * w
    opaque_cells = np.sum(opaque)
    transparent_cells = total_cells - opaque_cells
    
    print(f"Total cells: {total_cells}")
    print(f"Opaque cells: {opaque_cells}")
    print(f"Transparent cells: {transparent_cells}")
    
    # Check for opaque cells with non-zero transparency
    bad_cells = (opaque == 1) & (transparency > 0.0)
    if np.any(bad_cells):
        count = np.sum(bad_cells)
        print(f"\n❌ BUG FOUND: {count} opaque cells have transparency > 0!")
        coords = np.argwhere(bad_cells)[:5]  # Show first 5
        for y, x in coords:
            print(f"   Cell ({x},{y}): opaque={opaque[y,x]}, transparency={transparency[y,x]:.4f}")
        return  # Critical bug, stop here
    else:
        print("\n✓ All opaque cells have transparency = 0.0")
    
    # Check for transparent cells with non-one transparency
    transparent_but_not_one = (opaque == 0) & (transparency != 1.0)
    if np.any(transparent_but_not_one):
        count = np.sum(transparent_but_not_one)
        print(f"\n⚠ WARNING: {count} transparent cells have transparency != 1.0")
        print("   This may be intentional (partial transparency) or a bug.")
        coords = np.argwhere(transparent_but_not_one)[:3]
        for y, x in coords:
            print(f"   Cell ({x},{y}): opaque={opaque[y,x]}, transparency={transparency[y,x]:.4f}")
    else:
        print("✓ All transparent cells have transparency = 1.0")
    
    print()


def check_fov_visibility(
    visible: NDArray[np.uint8],
    visibility: NDArray[np.float32],
    opaque: NDArray[np.uint8],
    src_x: int,
    src_y: int,
) -> None:
    """Verify FOV visibility values are correct."""
    print("="*60)
    print("DIAGNOSTIC 2: FOV Visibility Values")
    print("="*60)
    
    print(f"Light source at: ({src_x}, {src_y})")
    print(f"Cells marked visible: {np.sum(visible)}")
    print(f"Cells with visibility > 0: {np.sum(visibility > 0.0)}")
    
    # Check source tile
    source_vis = visibility[src_y, src_x]
    if abs(source_vis - 1.0) < 0.001:
        print(f"✓ Source tile has visibility = {source_vis:.4f}")
    else:
        print(f"❌ BUG: Source tile has visibility = {source_vis:.4f} (should be 1.0)")
    
    # Check cells behind walls
    # Show visibility map
    print("\nVisibility map (first 9x9):")
    print("   ", end="")
    for x in range(min(9, visibility.shape[1])):
        print(f"{x:5}", end="")
    print()
    for y in range(min(9, visibility.shape[0])):
        print(f"{y:2}:", end="")
        for x in range(min(9, visibility.shape[1])):
            if opaque[y, x]:
                print("  ##" if visibility[y, x] > 0 else "  --", end=" ")
            else:
                val = visibility[y, x]
                if val > 0.001:
                    print(f"{val:4.2f}", end=" ")
                else:
                    print("   .", end=" ")
        print()
    
    print("\nLegend: ## = opaque+visible, -- = opaque+invisible, . = empty+invisible, 0.XX = visibility value")
    print()


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Generate points along Bresenham line (excluding endpoints)."""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    x, y = x0, y0
    
    if dy <= dx:
        err = dx // 2
        while True:
            x += sx
            err -= dy
            if err < 0:
                y += sy
                err += dx
            if x == x1 and y == y1:
                break
            points.append((x, y))
    else:
        err = dy // 2
        while True:
            y += sy
            err -= dx
            if err < 0:
                x += sx
                err += dy
            if x == x1 and y == y1:
                break
            points.append((x, y))
    
    return points


def check_line_of_sight_leaks(
    out_side_rgba: NDArray[np.float32],
    opaque: NDArray[np.uint8],
    visibility: NDArray[np.float32],
    src_x: int,
    src_y: int,
    target_x: int,
    target_y: int,
) -> None:
    """Check if specific target behind wall is lit."""
    print("="*60)
    print("DIAGNOSTIC 3: Line-of-Sight Leak Check")
    print("="*60)
    
    # Check the specific target
    total_alpha = np.sum(out_side_rgba[:, :, :, 3], axis=2)
    target_alpha = total_alpha[target_y, target_x]
    target_vis = visibility[target_y, target_x]
    target_opaque = opaque[target_y, target_x]
    
    print(f"\nTarget cell ({target_x}, {target_y}):")
    print(f"  Opaque: {target_opaque}")
    print(f"  Visibility: {target_vis:.4f}")
    print(f"  Alpha (light): {target_alpha:.4f}")
    
    # Check line from source to target
    print(f"\nLine-of-sight from ({src_x},{src_y}) to ({target_x},{target_y}):")
    line = bresenham_line(src_x, src_y, target_x, target_y)
    
    blocker_found = None
    for i, (bx, by) in enumerate(line):
        blocks = opaque[by, bx]
        trans = 0.0 if blocks else 1.0  # Simplified
        vis = visibility[by, bx]
        print(f"  Step {i+1}: ({bx},{by}) - opaque={blocks}, visibility={vis:.4f}")
        
        if blocks and blocker_found is None:
            blocker_found = (bx, by)
            print(f"         ^^^ FIRST BLOCKER")
    
    # Verdict
    print("\n" + "="*60)
    if target_alpha > 0.01:
        if blocker_found:
            print("❌ LIGHT LEAK DETECTED!")
            print(f"   Light reaches ({target_x},{target_y}) despite blocker at {blocker_found}")
            print(f"   Target has alpha={target_alpha:.4f} (should be 0.0)")
        else:
            print("✓ Target is lit and has clear line of sight")
    else:
        if blocker_found:
            print("✓ CORRECT: Target is blocked and not lit")
        else:
            print("⚠ Target has clear line of sight but is not lit (might be out of range)")
    
    print("="*60)
    print()


def run_complete_diagnostic() -> None:
    """Run complete diagnostic suite."""
    print("\n" + "="*70)
    print(" "*15 + "LIGHT LEAKAGE DIAGNOSTIC SUITE")
    print("="*70 + "\n")
    
    # Create test scene
    print("Setting up test scene...")
    dungeon, light_source, target_x, target_y = create_simple_test_scene()
    
    # Print layout
    print_dungeon_layout(dungeon, light_source.x, light_source.y, target_x, target_y)
    
    # Pre-check blocks_light implementation
    check_blocks_light_implementation(dungeon)
    
    # Build transparency arrays
    print("Building transparency arrays...")
    h, w = dungeon.height, dungeon.width
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.zeros((h, w), dtype=np.float32)
    
    for y in range(h):
        for x in range(w):
            blocks = dungeon.blocks_light(x, y)
            opaque[y, x] = np.uint8(1) if blocks else np.uint8(0)
            transparency[y, x] = np.float32(0.0) if blocks else np.float32(1.0)
    
    # Check transparency array
    check_transparency_array(opaque, transparency)
    
    # Run FOV
    print("Running FOV calculation...")
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)
    visibility = np.zeros((h, w), dtype=np.float32)
    
    compute_fov_all_octants(
        opaque,
        transparency,
        visible,
        dist,
        side_bits,
        visibility,
        light_source.x,
        light_source.y,
        light_source.light_radius,
    )
    
    # Check FOV visibility
    check_fov_visibility(visible, visibility, opaque, light_source.x, light_source.y)
    
    # Create Light object for lighting calculation
    print("Running lighting calculation...")
    light = Light(
        x=light_source.x,
        y=light_source.y,
        radius=light_source.light_radius,
        intensity=1.0,
        color_rgb=light_source.base_color_rgb,
        height=light_source.height,
    )
    
    # Create LightContext and compute lighting
    ctx = LightContext(width=w, height=h, ambient=(0, 0, 0))
    ctx.update_all_lights(
        lights=[light],
        opaque=opaque,
        transparency=transparency,
    )
    
    # Check line-of-sight leaks
    check_line_of_sight_leaks(
        ctx.side_rgba,
        opaque,
        visibility,
        light_source.x,
        light_source.y,
        target_x,
        target_y,
    )
    
    # Final summary
    print("\n" + "="*70)
    print("DIAGNOSTIC COMPLETE")
    print("="*70)
    print("\nIf light leaks were detected, check:")
    print("1. Does blocks_light() return True for ALL opaque tiles?")
    print("2. Is the transparency array correctly constructed?")
    print("3. Does FOV give visibility=0.0 for cells behind walls?")
    print("4. Is the lighting code using the CORRECTED version?")
    print()


if __name__ == "__main__":
    try:
        run_complete_diagnostic()
    except Exception as e:
        print(f"\n❌ Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()
        print("\nCommon issues:")
        print("- Missing modules in /mnt/user-data/uploads")
        print("- Module import errors")
        print("- Incorrect file paths")

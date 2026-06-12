#!/usr/bin/env python3

# Geographic stats reserved for the chronicler (not consumed by the UI). User-facing docs: `tools/tools.md`.

import sys
from collections import deque
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import emit, load_save, parse_sections  # noqa: E402

_ALL_SECTIONS = ("basic",)
_MIN_ISLAND_SIZE = 80  # WB UI drops sub-80-tile noise patches — empirical match against in-game « Îles » counter.
_NON_LAND_BIOMES = {"close_ocean", "deep_ocean", "lava3", "shallow_waters"}


def _build_basic(save: dict) -> dict:
    return {"islands": _count_land_islands(save)}


# 4-conn BFS flood-fill on land tiles, skipping islands below `_MIN_ISLAND_SIZE` to mirror WB's `IslandsCalculator.countLandIslands`.
def _count_land_islands(save: dict) -> int:
    tile_map = save.get("tileMap") or []
    non_land = {i for i, name in enumerate(tile_map) if name in _NON_LAND_BIOMES}
    grid = _decode_tile_grid(save)
    if not grid:
        return 0
    width, height = len(grid[0]), len(grid)
    visited = [[False] * width for _ in range(height)]
    count = 0
    for start_y in range(height):
        for start_x in range(width):
            if visited[start_y][start_x] or grid[start_y][start_x] in non_land:
                continue
            size = 0
            queue = deque([(start_x, start_y)])
            visited[start_y][start_x] = True
            while queue:
                x, y = queue.popleft()
                size += 1
                for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx] and grid[ny][nx] not in non_land:
                        visited[ny][nx] = True
                        queue.append((nx, ny))
            if size >= _MIN_ISLAND_SIZE:
                count += 1
    return count


# Expand the save's per-row RLE (`tileArray` = tile ids, `tileAmounts` = run lengths) into a 2D `grid[y][x]` of tile ids.
def _decode_tile_grid(save: dict) -> list[list[int]]:
    grid = []
    for ids, runs in zip(save.get("tileArray") or [], save.get("tileAmounts") or []):
        row = []
        for tile_id, n in zip(ids, runs):
            row.extend([tile_id] * n)
        grid.append(row)
    return grid


def main(argv: list[str]) -> int:
    try:
        sections = parse_sections(argv[0] if argv else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save()
    out: dict = {}
    if "basic" in sections:
        out["basic"] = _build_basic(save)
    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Resolve a subspecies' chromosomes to gene-level stat contributions.

Usage: python3 stats.py <subspecies_id>

Reads the live save (cf. `CURRENT_SAVE`) — chromosomes are stable per subspecies so no
chapter arg is needed. The chronicler reads `actor.subspecies` from the save then passes
that id here.

Returns the SUM of every gene's contribution to base stats, applying BAD / GOLDEN modifiers
per `chronicler.md § VI`. Output is the **chromosome-level** part of the subspecies' base —
the chronicler still adds trait bonuses, species template stats, items, etc. on top.

Output: `id | <stat>=<value>,...` (alphabetical, empty values dropped).
"""
# ─── Maintenance / algorithm reference ───
# Full algorithm spec: `chronicler.md § VI` ("Annexe technique — Génétique et stats de base").
# All numeric tables (GENE_VALUES, GENE_INDEX, ceil-on-bad exceptions, synergy-always genes)
# are sourced from that section + observation of WorldBox in-game tooltips.
#
# Pipeline per chromosome:
#   1. For each locus (skipping `void_loci`):
#        a. Detect BAD: at least one cardinal neighbor (N/S/E/W) contains the `bad` gene.
#        b. Detect GOLDEN: every non-border side synergizes (≥1 synergized side, all of them
#           synergized). BAD has priority over GOLDEN.
#        c. Apply tier: BAD → floor(v/2) (or ceil for `attack_speed`/`damage_1`/`health_1`/
#           `speed_1`); GOLDEN → v×2; else v as-is.
#        d. Accumulate per stat name.
#   2. Round any float result to 4 decimals, cast integer-equivalents to int, drop zeros.
#
# Color synergy uses .NET `System.Random` seeded with `life_dna + gene.GENE_INDEX` to derive
# each gene's 4-side color signature. The port mirrors .NET's int32 overflow semantics — see
# `to_int32()` and `SystemRandom`. Color positions per chronicler.md spec use indices on a
# *spaced* text (`"XXX XXX XXX XXX XXX"`, 19 chars) at 0/8/10/18 → in our unspaced 15-char
# text those map to 0/6/8/14. ⚠️ If you ever rewrite the DNA generator to keep the spaces,
# remember to shift the indices back.
#
# `gene_colors` is `@cache`d — each call to `is_golden` traverses 4 neighbors and calls
# `gene_colors` for both gene and neighbor twice on average, so re-init of SystemRandom (a
# 220-iteration setup loop) dominated runtime without caching.
#
# Known edge case: `is_bad` does NOT currently check `void_set` — a voided locus containing
# the `bad` gene would still trigger BAD on neighbors. None of our observed subspecies
# place `bad` on a voided locus, but if a divergence appears, gate on void_set here.
import json
import sys
import zlib
from functools import cache
from pathlib import Path

# macOS path — mirror chronicler.md § "Emplacement source des saves WorldBox".
CURRENT_SAVE = Path.home() / 'Library/Application Support/mkarpenko/WorldBox/saves/save1/map.wbox'

GRID_COLS = 6

# Per chronicler.md § VI — gene -> (stat name, value contribution).
GENE_VALUES = {
    'armor_1': ('armor', 1), 'armor_2': ('armor', 6), 'armor_3': ('armor', 10),
    'attack_speed': ('attack_speed', 1),
    'birth_rate_1': ('birth_rate', 1),
    'damage_1': ('damage', 1), 'damage_2': ('damage', 6), 'damage_3': ('damage', 10),
    'diplomacy_1': ('diplomacy', 1), 'diplomacy_2': ('diplomacy', 2), 'diplomacy_3': ('diplomacy', 3),
    'health_1': ('health', 1), 'health_2': ('health', 10), 'health_3': ('health', 50),
    'health_4': ('health', 100), 'health_5': ('health', 300),
    'intelligence_1': ('intelligence', 1), 'intelligence_2': ('intelligence', 2), 'intelligence_3': ('intelligence', 3),
    'lifespan_1': ('lifespan', 5), 'lifespan_2': ('lifespan', 20),
    'lifespan_3': ('lifespan', 50), 'lifespan_4': ('lifespan', 100),
    'offspring_1': ('offspring', 1), 'offspring_2': ('offspring', 3),
    'offspring_3': ('offspring', 5), 'offspring_4': ('offspring', 10),
    'scale_minus': ('scale', -0.01), 'scale_plus': ('scale', 0.03),
    'speed_1': ('speed', 1), 'speed_2': ('speed', 2), 'speed_3': ('speed', 5),
    'stamina_1': ('stamina', 10), 'stamina_2': ('stamina', 50), 'stamina_3': ('stamina', 100),
    'stewardship_1': ('stewardship', 1), 'stewardship_2': ('stewardship', 2), 'stewardship_3': ('stewardship', 3),
    'warfare_1': ('warfare', 1), 'warfare_2': ('warfare', 2), 'warfare_3': ('warfare', 3),
}
# Genes that round UP on BAD (instead of down).
CEIL_ON_BAD = {'attack_speed', 'damage_1', 'health_1', 'speed_1'}
SYNERGY_ALWAYS = {'bonus_female', 'bonus_male', 'mutagenic'}

# Gene index_id used to seed SystemRandom — order in `GeneLibrary`
# (`addSpecial` → `addBaseStats` → `addFightStats` → `addBonusStats` → `addAttributes`).
GENE_INDEX = {
    'empty': 1, 'temp_for_generation': 2, 'bad': 3,
    'bonus_male': 4, 'bonus_female': 5, 'mutagenic': 6,
    'birth_rate_1': 7,
    'offspring_1': 8, 'offspring_2': 9, 'offspring_3': 10, 'offspring_4': 11,
    'lifespan_1': 12, 'lifespan_2': 13, 'lifespan_3': 14, 'lifespan_4': 15,
    'health_1': 16, 'health_2': 17, 'health_3': 18, 'health_4': 19, 'health_5': 20,
    'stamina_1': 21, 'stamina_2': 22, 'stamina_3': 23,
    'speed_1': 24, 'speed_2': 25, 'speed_3': 26,
    'armor_1': 27, 'armor_2': 28, 'armor_3': 29,
    'damage_1': 30, 'damage_2': 31, 'damage_3': 32,
    'attack_speed': 33, 'scale_plus': 34, 'scale_minus': 35,
    'diplomacy_1': 36, 'diplomacy_2': 37, 'diplomacy_3': 38,
    'warfare_1': 39, 'warfare_2': 40, 'warfare_3': 41,
    'stewardship_1': 42, 'stewardship_2': 43, 'stewardship_3': 44,
    'intelligence_1': 45, 'intelligence_2': 46, 'intelligence_3': 47,
}

COLOR_MAP = {'T': 'red', 'G': 'yellow', 'A': 'green', 'C': 'blue'}


# Mirrors C# int32 wrap-around — required because the game's SystemRandom relies on it.
def to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


# Faithful port of .NET `System.Random` (subtractive generator). Constants and seed loop
# match the reference .NET implementation — do not "simplify" without verifying outputs.
class SystemRandom:

    MBIG = 2147483647
    MSEED = 161803398

    def __init__(self, seed: int):
        self.inext, self.inextp = 0, 21
        sa = self.SeedArray = [0] * 56
        subtraction = 0x7FFFFFFF if seed == -0x80000000 else abs(seed)
        mj = to_int32(self.MSEED - subtraction)
        sa[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            sa[ii] = mk
            mk = to_int32(mj - mk)
            if mk < 0: mk += self.MBIG
            mj = sa[ii]
        for _ in range(4):
            for i in range(1, 56):
                sa[i] = to_int32(sa[i] - sa[1 + (i + 30) % 55])
                if sa[i] < 0: sa[i] += self.MBIG

    def _internal_sample(self) -> int:
        ln = (self.inext + 1) if (self.inext + 1) < 56 else 1
        lnp = (self.inextp + 1) if (self.inextp + 1) < 56 else 1
        r = to_int32(self.SeedArray[ln] - self.SeedArray[lnp])
        if r == self.MBIG: r -= 1
        if r < 0: r += self.MBIG
        self.SeedArray[ln] = r
        self.inext, self.inextp = ln, lnp
        return r

    def Next(self, mv: int) -> int:
        return int((self._internal_sample() / self.MBIG) * mv)


# Returns {left, up, down, right} colors for a gene's DNA strand. Memoized: each gene's
# colors only depend on (gene, life_dna), and life_dna is constant for one run.
@cache
def gene_colors(gene: str, life_dna: int) -> dict:
    idx = GENE_INDEX.get(gene)
    if idx is None: return {}
    rnd = SystemRandom(to_int32(life_dna + idx))
    text = ''.join('ACGT'[rnd.Next(4)] for _ in range(15))
    return {'left': COLOR_MAP[text[0]], 'up': COLOR_MAP[text[6]],
            'down': COLOR_MAP[text[8]], 'right': COLOR_MAP[text[14]]}


# `dx`/`dy` → which side of the current gene faces the neighbor.
SIDE = {(1, 0): 'right', (-1, 0): 'left', (0, 1): 'down', (0, -1): 'up'}
OPPOSITE = {(1, 0): 'left', (-1, 0): 'right', (0, 1): 'up', (0, -1): 'down'}
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


# Returns (gene, idx) of neighbor, or (None, ...) for border (off-grid or voided).
def neighbor(loci: list[str], void_set: set[int], idx: int, dx: int, dy: int) -> tuple[str | None, int]:
    rows = len(loci) // GRID_COLS
    x, y = idx % GRID_COLS, idx // GRID_COLS
    nx, ny = x + dx, y + dy
    if nx < 0 or nx >= GRID_COLS or ny < 0 or ny >= rows: return None, -1
    nidx = nx + ny * GRID_COLS
    if nidx in void_set: return None, nidx
    return loci[nidx], nidx


def synergizes(gene: str, ngene: str, dx: int, dy: int, super_set: set[int],
               my_idx: int, n_idx: int, life_dna: int) -> bool:
    my_super = my_idx in super_set
    n_super = n_idx in super_set
    if my_super and n_super: return False           # two amplifiers don't synergize with each other
    if my_super or n_super: return True             # amplifier synergizes with anything
    if gene in SYNERGY_ALWAYS or ngene in SYNERGY_ALWAYS: return True
    if gene == 'empty' or ngene == 'empty': return False
    return gene_colors(gene, life_dna).get(SIDE[dx, dy]) == gene_colors(ngene, life_dna).get(OPPOSITE[dx, dy])


def is_bad(loci: list[str], idx: int) -> bool:
    rows = len(loci) // GRID_COLS
    x, y = idx % GRID_COLS, idx // GRID_COLS
    for dx, dy in DIRECTIONS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < GRID_COLS and 0 <= ny < rows and loci[nx + ny * GRID_COLS] == 'bad':
            return True
    return False


def is_golden(loci: list[str], idx: int, void_set: set[int], super_set: set[int], life_dna: int) -> bool:
    gene = loci[idx]
    non_border = synergized = 0
    for dx, dy in DIRECTIONS:
        ngene, nidx = neighbor(loci, void_set, idx, dx, dy)
        if ngene is None: continue
        non_border += 1
        if synergizes(gene, ngene, dx, dy, super_set, idx, nidx, life_dna):
            synergized += 1
    return synergized >= 1 and synergized == non_border


# BAD → floor(v/2) (or ceil for the few `_1`-tier genes listed in CEIL_ON_BAD); GOLDEN → v×2.
def apply_tier(gene: str, value: float, bad: bool, golden: bool) -> float:
    if bad: return -(-value // 2) if gene in CEIL_ON_BAD else value // 2
    return value * 2 if golden else value


def process_chromosomes(sub: dict, life_dna: int) -> dict:
    totals: dict[str, float] = {}
    for chrom in sub.get('saved_chromosome_data') or []:
        loci = chrom.get('loci') or []
        void_set = set(chrom.get('void_loci') or [])
        super_set = set(chrom.get('super_loci') or [])
        for idx, gene in enumerate(loci):
            if idx in void_set: continue
            entry = GENE_VALUES.get(gene)
            if entry is None: continue
            stat, value = entry
            bad = is_bad(loci, idx)
            golden = (not bad) and is_golden(loci, idx, void_set, super_set, life_dna)
            totals[stat] = totals.get(stat, 0) + apply_tier(gene, value, bad, golden)
    # Round floats to 4 decimals, cast integer-equivalents to int, drop zeros.
    result = {}
    for k, v in totals.items():
        if isinstance(v, float):
            v = round(v, 4)
            if v.is_integer(): v = int(v)
        if v: result[k] = v
    return result


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    try: sub_id = int(argv[0])
    except ValueError:
        print(f'invalid id: {argv[0]}', file=sys.stderr)
        return 1
    if not CURRENT_SAVE.exists():
        print(f'no save found at {CURRENT_SAVE}', file=sys.stderr)
        return 2
    with CURRENT_SAVE.open('rb') as f:
        save = json.loads(zlib.decompress(f.read()))
    sub = next((s for s in save.get('subspecies', []) if s.get('id') == sub_id), None)
    if sub is None:
        print(f'unknown subspecies: {sub_id}', file=sys.stderr)
        return 1

    life_dna = int(save['mapStats'].get('life_dna') or 0)
    totals = process_chromosomes(sub, life_dna)
    stats_str = ','.join(f'{k}={v}' for k, v in sorted(totals.items()))
    print(f"{sub_id} | {stats_str}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

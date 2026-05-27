#!/usr/bin/env python3

# User-facing docs (usage, available sections) live in `tools/tools.md`. The notes
# below are for maintainers — algorithm references, gotchas, source pointers.
#
# ─── Maintenance / algorithm reference ───
# Full algorithm spec: `chronicler.md § VI` ("Annexe technique — Génétique et stats de base").
# All numeric tables (_GENE_VALUES, _GENE_INDEX, ceil-on-bad exceptions, synergy-always genes)
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
# Color synergy uses .NET `System.Random` seeded with `life_dna + gene._GENE_INDEX` to derive
# each gene's 4-side color signature. The port mirrors .NET's int32 overflow semantics — see
# `_to_int32()` and `_SystemRandom`. Color positions per chronicler.md spec use indices on a
# *spaced* text (`"XXX XXX XXX XXX XXX"`, 19 chars) at 0/8/10/18 → in our unspaced 15-char
# text those map to 0/6/8/14. ⚠️ If you ever rewrite the DNA generator to keep the spaces,
# remember to shift the indices back.

import json
import math
import re
import sys
from functools import cache
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import CURRENT_SAVE, load_save, parse_sections  # noqa: E402

_ALL_SECTIONS = ("best_friend", "creature_traits", "equipment", "inventory", "lover", "metadata", "plot", "ranks_in_species", "stats")
_DATAS_DIR = Path(__file__).parent.parent / "datas"
_GRID_COLS = 6
_LEVEL_RE = re.compile(r"(\d+)$")
_MONTHS_PER_YEAR = 60

_CLAN_TRAITS_DATA = _DATAS_DIR / "clan-traits.json"
_CREATURE_TRAITS_DATA = _DATAS_DIR / "creature-traits.json"
_EQUIPMENT_DATA = _DATAS_DIR / "equipment.json"
_LANGUAGE_TRAITS_DATA = _DATAS_DIR / "language-traits.json"
_SPECIES_DATA = _DATAS_DIR / "species.json"
_SUBSPECIES_TRAITS_DATA = _DATAS_DIR / "subspecies-traits.json"


# Per chronicler.md § VI — gene -> (stat name, value contribution).
_GENE_VALUES = {
    "armor_1": ("armor", 1),
    "armor_2": ("armor", 6),
    "armor_3": ("armor", 10),
    "attack_speed": ("attack_speed", 1),
    "birth_rate_1": ("birth_rate", 1),
    "damage_1": ("damage", 1),
    "damage_2": ("damage", 6),
    "damage_3": ("damage", 10),
    "diplomacy_1": ("diplomacy", 1),
    "diplomacy_2": ("diplomacy", 2),
    "diplomacy_3": ("diplomacy", 3),
    "health_1": ("health", 1),
    "health_2": ("health", 10),
    "health_3": ("health", 50),
    "health_4": ("health", 100),
    "health_5": ("health", 300),
    "intelligence_1": ("intelligence", 1),
    "intelligence_2": ("intelligence", 2),
    "intelligence_3": ("intelligence", 3),
    "lifespan_1": ("lifespan", 5),
    "lifespan_2": ("lifespan", 20),
    "lifespan_3": ("lifespan", 50),
    "lifespan_4": ("lifespan", 100),
    "offspring_1": ("offspring", 1),
    "offspring_2": ("offspring", 3),
    "offspring_3": ("offspring", 5),
    "offspring_4": ("offspring", 10),
    "scale_minus": ("scale", -0.01),
    "scale_plus": ("scale", 0.03),
    "speed_1": ("speed", 1),
    "speed_2": ("speed", 2),
    "speed_3": ("speed", 5),
    "stamina_1": ("stamina", 10),
    "stamina_2": ("stamina", 50),
    "stamina_3": ("stamina", 100),
    "stewardship_1": ("stewardship", 1),
    "stewardship_2": ("stewardship", 2),
    "stewardship_3": ("stewardship", 3),
    "warfare_1": ("warfare", 1),
    "warfare_2": ("warfare", 2),
    "warfare_3": ("warfare", 3),
}

# Genes that round UP on BAD (instead of down).
_CEIL_ON_BAD = {"attack_speed", "damage_1", "health_1", "speed_1"}
_SYNERGY_ALWAYS = {"bonus_female", "bonus_male", "mutagenic"}

# Gene index_id used to seed SystemRandom — order in `GeneLibrary` (`addSpecial` → `addBaseStats` → `addFightStats` → `addBonusStats` → `addAttributes`).
_GENE_INDEX = {
    "empty": 1,
    "temp_for_generation": 2,
    "bad": 3,
    "bonus_male": 4,
    "bonus_female": 5,
    "mutagenic": 6,
    "birth_rate_1": 7,
    "offspring_1": 8,
    "offspring_2": 9,
    "offspring_3": 10,
    "offspring_4": 11,
    "lifespan_1": 12,
    "lifespan_2": 13,
    "lifespan_3": 14,
    "lifespan_4": 15,
    "health_1": 16,
    "health_2": 17,
    "health_3": 18,
    "health_4": 19,
    "health_5": 20,
    "stamina_1": 21,
    "stamina_2": 22,
    "stamina_3": 23,
    "speed_1": 24,
    "speed_2": 25,
    "speed_3": 26,
    "armor_1": 27,
    "armor_2": 28,
    "armor_3": 29,
    "damage_1": 30,
    "damage_2": 31,
    "damage_3": 32,
    "attack_speed": 33,
    "scale_plus": 34,
    "scale_minus": 35,
    "diplomacy_1": 36,
    "diplomacy_2": 37,
    "diplomacy_3": 38,
    "warfare_1": 39,
    "warfare_2": 40,
    "warfare_3": 41,
    "stewardship_1": 42,
    "stewardship_2": 43,
    "stewardship_3": 44,
    "intelligence_1": 45,
    "intelligence_2": 46,
    "intelligence_3": 47,
}

_COLOR_MAP = {"T": "red", "G": "yellow", "A": "green", "C": "blue"}
_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_OPPOSITE = {(1, 0): "left", (-1, 0): "right", (0, 1): "up", (0, -1): "down"}
_SIDE = {(1, 0): "right", (-1, 0): "left", (0, 1): "down", (0, -1): "up"}

# Per `SimGlobalAsset.ctor` IL → static level_mod_bonus_* / _MANA_PER_INTELLIGENCE constants.
_LEVEL_MOD = {"health": 0.05, "mana": 0.02, "stamina": 0.02}
_LEVEL_VETERAN_SKILL_BONUS = 0.1
_LEVEL_VETERAN_THRESHOLD = 5
_MANA_PER_INTELLIGENCE = 10

_RENAMES = {"cities": "max_cities", "health": "health_max", "mana": "mana_max", "offspring": "max_children", "stamina": "stamina_max"}

# Stats kept as 1-decimal floats — integer truncate would lose meaningful precision (damage_range is typically `damage × ratio` where ratio < 1).
_KEEP_DECIMAL = {"damage_range"}

# Stats dropped from the output — never consumed by the chronicler UI or fixtures. Add new
# stats here when they enter the pipeline but aren't surfaced (audit via chapter.interface.ts).
_DROP = {"accuracy", "critical_damage_multiplier", "knockback", "loyalty_traits", "mass", "mass_2", "range", "targets"}


# Mirrors C# int32 wrap-around — required because the game's SystemRandom relies on it.
def _to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


# Faithful port of .NET `System.Random` (subtractive generator). Constants and seed loop
# match the reference .NET implementation — do not "simplify" without verifying outputs.
class _SystemRandom:
    MBIG = 2147483647
    MSEED = 161803398

    def __init__(self, seed: int):
        self.inext, self.inextp = 0, 21
        sa = self.SeedArray = [0] * 56
        subtraction = 0x7FFFFFFF if seed == -0x80000000 else abs(seed)
        mj = _to_int32(self.MSEED - subtraction)
        sa[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            sa[ii] = mk
            mk = _to_int32(mj - mk)
            if mk < 0:
                mk += self.MBIG
            mj = sa[ii]
        for _ in range(4):
            for i in range(1, 56):
                sa[i] = _to_int32(sa[i] - sa[1 + (i + 30) % 55])
                if sa[i] < 0:
                    sa[i] += self.MBIG

    def _internal_sample(self) -> int:
        ln = (self.inext + 1) if (self.inext + 1) < 56 else 1
        lnp = (self.inextp + 1) if (self.inextp + 1) < 56 else 1
        r = _to_int32(self.SeedArray[ln] - self.SeedArray[lnp])
        if r == self.MBIG:
            r -= 1
        if r < 0:
            r += self.MBIG
        self.SeedArray[ln] = r
        self.inext, self.inextp = ln, lnp
        return r

    def Next(self, mv: int) -> int:
        return int((self._internal_sample() / self.MBIG) * mv)


# Returns {left, up, down, right} colors for a gene's DNA strand. Memoized: each gene's
# colors only depend on (gene, life_dna), and life_dna is constant for one run.
@cache
def _gene_colors(gene: str, life_dna: int) -> dict:
    idx = _GENE_INDEX.get(gene)
    if idx is None:
        return {}
    rnd = _SystemRandom(_to_int32(life_dna + idx))
    text = "".join("ACGT"[rnd.Next(4)] for _ in range(15))
    return {"left": _COLOR_MAP[text[0]], "up": _COLOR_MAP[text[6]], "down": _COLOR_MAP[text[8]], "right": _COLOR_MAP[text[14]]}


def _neighbor(loci: list[str], void_set: set[int], idx: int, dx: int, dy: int) -> tuple[str | None, int]:
    rows = len(loci) // _GRID_COLS
    x, y = idx % _GRID_COLS, idx // _GRID_COLS
    nx, ny = x + dx, y + dy
    if nx < 0 or nx >= _GRID_COLS or ny < 0 or ny >= rows:
        return None, -1
    nidx = nx + ny * _GRID_COLS
    if nidx in void_set:
        return None, nidx
    return loci[nidx], nidx


def _synergizes(gene: str, ngene: str, dx: int, dy: int, super_set: set[int], my_idx: int, n_idx: int, life_dna: int) -> bool:
    my_super = my_idx in super_set
    n_super = n_idx in super_set
    if my_super and n_super:
        return False  # two amplifiers don't synergize with each other
    if my_super or n_super:
        return True  # amplifier synergizes with anything
    if gene in _SYNERGY_ALWAYS or ngene in _SYNERGY_ALWAYS:
        return True
    if gene == "empty" or ngene == "empty":
        return False
    return _gene_colors(gene, life_dna).get(_SIDE[dx, dy]) == _gene_colors(ngene, life_dna).get(_OPPOSITE[dx, dy])


def _is_bad(loci: list[str], idx: int) -> bool:
    rows = len(loci) // _GRID_COLS
    x, y = idx % _GRID_COLS, idx // _GRID_COLS
    for dx, dy in _DIRECTIONS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < _GRID_COLS and 0 <= ny < rows and loci[nx + ny * _GRID_COLS] == "bad":
            return True
    return False


def _is_golden(loci: list[str], idx: int, void_set: set[int], super_set: set[int], life_dna: int) -> bool:
    gene = loci[idx]
    non_border = synergized = 0
    for dx, dy in _DIRECTIONS:
        ngene, nidx = _neighbor(loci, void_set, idx, dx, dy)
        if ngene is None:
            continue
        non_border += 1
        if _synergizes(gene, ngene, dx, dy, super_set, idx, nidx, life_dna):
            synergized += 1
    return synergized >= 1 and synergized == non_border


# BAD → floor(v/2) (or ceil for the few `_1`-tier genes listed in _CEIL_ON_BAD); GOLDEN → v×2.
def _apply_tier(gene: str, value: float, bad: bool, golden: bool) -> float:
    if bad:
        return -(-value // 2) if gene in _CEIL_ON_BAD else value // 2
    return value * 2 if golden else value


def _add_chromosome_stats(totals: dict, sub: dict, life_dna: int) -> None:
    for chrom in sub.get("saved_chromosome_data") or []:
        loci = chrom.get("loci") or []
        void_set = set(chrom.get("void_loci") or [])
        super_set = set(chrom.get("super_loci") or [])
        for idx, gene in enumerate(loci):
            if idx in void_set:
                continue
            entry = _GENE_VALUES.get(gene)
            if entry is None:
                continue
            stat, value = entry
            bad = _is_bad(loci, idx)
            golden = (not bad) and _is_golden(loci, idx, void_set, super_set, life_dna)
            totals[stat] = totals.get(stat, 0) + _apply_tier(gene, value, bad, golden)


def _add_trait_stats(totals: dict, trait_ids: list[str], traits_data: dict) -> None:
    for trait_id in trait_ids or []:
        entry = traits_data.get(trait_id) or {}
        for k, v in (entry.get("stats") or {}).items():
            totals[k] = totals.get(k, 0) + v


def _add_species_stats(totals: dict, asset_id: str, species_data: dict) -> None:
    for k, v in ((species_data.get(asset_id) or {}).get("stats") or {}).items():
        totals[k] = totals.get(k, 0) + v


# Sums each equipped item's base stats + the stats of every applied modifier.
def _add_equipment_stats(totals: dict, item_ids: list[int], items_by_id: dict, item_stats: dict, mod_stats: dict) -> None:
    for iid in item_ids or []:
        item = items_by_id.get(iid)
        if item is None:
            continue
        for k, v in (item_stats.get(item["asset_id"]) or {}).items():
            totals[k] = totals.get(k, 0) + v
        for mod in item.get("modifiers") or []:
            for k, v in (mod_stats.get(mod) or {}).items():
                totals[k] = totals.get(k, 0) + v


# Flat additive bonuses applied late in `Actor.updateStats`:
#   stats["mana"] += int(stats["intelligence"] × _MANA_PER_INTELLIGENCE)
def _apply_intelligence_bonus(totals: dict) -> None:
    intel = totals.get("intelligence", 0)
    if intel:
        totals["mana"] = totals.get("mana", 0) + int(intel * _MANA_PER_INTELLIGENCE)


# Civil progression accumulator (`actor.custom_data_float`) — diplomacy / warfare / stewardship
# / intelligence each gain +1 per conversation / event / aging tick over the actor's life.
def _add_custom_data_float(totals: dict, custom: dict | None) -> None:
    for k, v in (custom or {}).items():
        totals[k] = totals.get(k, 0) + v


# Resolve every `multiplier_X` key as a coefficient on stats[X]: `final = base × (1 + multiplier)`.
def _apply_multipliers(totals: dict) -> None:
    for k in list(totals.keys()):
        if k.startswith("multiplier_"):
            target = k[len("multiplier_") :]
            if target in totals:
                totals[target] = totals[target] * (1 + totals[k])
            del totals[k]


# Final adjustments per `Actor.updateStats` + tooltip render:
#   • damage += warfare / 5                         (DLL: stats["damage"] += stats["warfare"] / 5)
#   • damage_range becomes the amplitude in raw hp  (DLL tooltip: int(damage * damage_range))
#   • critical_chance promoted to integer percent   (tooltip displays `28%`, raw is 0.28)
def _apply_damage_finalize(totals: dict) -> None:
    if "damage" in totals:
        totals["damage"] = totals["damage"] + totals.get("warfare", 0) / 5
    if "damage_range" in totals:
        totals["damage_range"] = totals.get("damage", 0) * totals["damage_range"]
    if "critical_chance" in totals:
        totals["critical_chance"] = totals["critical_chance"] * 100


# Per `Actor.calculateOffspringBasedOnAge`: scale `offspring` by an age-bracket multiplier
# so the displayed max matches the in-game tooltip (e.g. raw 3 → 2 for a mature actor).
def _apply_offspring_age_scaling(totals: dict, age_ratio: float) -> None:
    if "offspring" not in totals:
        return
    if age_ratio > 0.9:
        mult = 0.1
    elif age_ratio > 0.7:
        mult = 0.2
    elif age_ratio > 0.5:
        mult = 0.5
    elif age_ratio > 0.3:
        mult = 0.8
    else:
        mult = 1.0
    totals["offspring"] = math.ceil(totals["offspring"] * mult)


# Apply Actor.updateStats end-of-method level scaling: stat *= (1 + level × mult), and a flat +0.1 to skill_combat / skill_spell when level > 5.
def _apply_level_scaling(totals: dict, level: int) -> None:
    for stat, mult in _LEVEL_MOD.items():
        if stat in totals:
            totals[stat] = totals[stat] * (1 + level * mult)
    if level > _LEVEL_VETERAN_THRESHOLD:
        for stat in ("skill_combat", "skill_spell"):
            totals[stat] = totals.get(stat, 0) + _LEVEL_VETERAN_SKILL_BONUS


# Floor floats to int (game stores most stats as int32). `health` / `mana` are renamed to
# `health_max` / `mana_max` — the values represent the actor's post-pipeline maximum.
def _cleanup_stats(totals: dict) -> dict:
    result = {}
    for k, v in totals.items():
        if k in _DROP:
            continue
        if isinstance(v, float):
            v = round(v, 1) if k in _KEEP_DECIMAL else int(v)
        if v:
            result[_RENAMES.get(k, k)] = v
    return dict(sorted(result.items()))


def _build_context(save: dict) -> dict:
    # Index of living children per parent — matches `Actor.get_current_children_count`.
    children_by_parent: dict[int, int] = {}
    for actor in save.get("actors_data", []):
        for parent_id in (actor.get("parent_id_1"), actor.get("parent_id_2")):
            if parent_id:
                children_by_parent[parent_id] = children_by_parent.get(parent_id, 0) + 1
    return {
        "children_by_parent": children_by_parent,
        "clan_traits": json.load(_CLAN_TRAITS_DATA.open()),
        "clans_by_id": {c["id"]: c for c in save.get("clans", [])},
        "creature_traits": json.load(_CREATURE_TRAITS_DATA.open()),
        "equipment": json.load(_EQUIPMENT_DATA.open()),
        "items_by_id": {it["id"]: it for it in save["items"]},
        "language_traits": json.load(_LANGUAGE_TRAITS_DATA.open()),
        "languages_by_id": {lang["id"]: lang for lang in save.get("languages", [])},
        "life_dna": int(save["mapStats"].get("life_dna") or 0),
        "species_data": json.load(_SPECIES_DATA.open()),
        "subspecies_by_id": {s["id"]: s for s in save.get("subspecies", [])},
        "subspecies_traits": json.load(_SUBSPECIES_TRAITS_DATA.open()),
        "world_time": float(save["mapStats"].get("world_time") or 0),
    }


# Aggregate one actor's instant-T stats through the full pipeline. `subspecies_base_cache`
# is optional; when provided, the heavy (species + chromosomes + subspecies traits) base is
# computed once per subspecies and reused across actors — a 5× speedup when ranking.
def _compute_stats(actor: dict, ctx: dict, save: dict | None = None, subspecies_base_cache: dict | None = None) -> dict:
    sub_id = actor.get("subspecies")
    sub = ctx["subspecies_by_id"].get(sub_id) if sub_id is not None else None
    if sub is None:
        return {}
    base = subspecies_base_cache.get(sub_id) if subspecies_base_cache is not None else None
    if base is None:
        base = {}
        _add_species_stats(base, actor.get("asset_id", ""), ctx["species_data"])
        _add_chromosome_stats(base, sub, ctx["life_dna"])
        _add_trait_stats(base, sub.get("saved_traits") or [], ctx["subspecies_traits"])
        if subspecies_base_cache is not None:
            subspecies_base_cache[sub_id] = dict(base)
    totals = dict(base)
    _add_trait_stats(totals, actor.get("saved_traits") or [], ctx["creature_traits"])
    _add_trait_stats(totals, (ctx["clans_by_id"].get(actor.get("clan")) or {}).get("saved_traits") or [], ctx["clan_traits"])
    _add_trait_stats(totals, (ctx["languages_by_id"].get(actor.get("language")) or {}).get("saved_traits") or [], ctx["language_traits"])
    _add_equipment_stats(totals, actor.get("saved_items") or [], ctx["items_by_id"], ctx["equipment"]["items"], ctx["equipment"]["modifiers"])
    _add_custom_data_float(totals, actor.get("custom_data_float"))
    # WB scaling starts at level 1 even when the raw save field is absent / 0 (matches tooltip).
    _apply_level_scaling(totals, max(int(actor.get("level") or 0), 1))
    _apply_intelligence_bonus(totals)
    _apply_multipliers(totals)
    _apply_damage_finalize(totals)
    age_months = ctx["world_time"] - float(actor.get("created_time") or 0)
    lifespan_months = totals.get("lifespan", 0) * _MONTHS_PER_YEAR
    _apply_offspring_age_scaling(totals, age_months / lifespan_months if lifespan_months else 0)
    cleaned = _cleanup_stats(totals)
    # `max_cities` (Kingdom.getMaxCities) only matters for kings — strip it elsewhere.
    if save is not None and "king" not in _compute_roles(actor, save):
        cleaned.pop("max_cities", None)
    # Always-surface actor counters (kept verbatim even at 0 — the chronicler expects them).
    # `loot` keeps the WB-native name (the chronicler also reads it from the raw save).
    cleaned.update(
        {
            "births": int(actor.get("births") or 0),
            "children": ctx["children_by_parent"].get(actor.get("id"), 0),
            # Current `health`/`mana`/`stamina` (vs pipeline `*_max`); `happiness`/`nutrition` are live gauges with no max.
            "happiness": int(actor.get("happiness") or 0),
            "health": int(actor.get("health") or 0),
            "kills": int(actor.get("kills") or 0),
            # WB displays level 1 as the floor, even when the raw save field is absent / 0.
            "level": max(int(actor.get("level") or 0), 1),
            "loot": int(actor.get("loot") or 0),
            "mana": int(actor.get("mana") or 0),
            "money": int(actor.get("money") or 0),
            "nutrition": int(actor.get("nutrition") or 0),
            "renown": int(actor.get("renown") or 0),
            "stamina": int(actor.get("stamina") or 0),
        }
    )
    return dict(sorted(cleaned.items()))


# Standard competition rank (1,2,2,4) for every stats key, among the actor's same-`asset_id` peers.
# Ranks kept in the JSON. Most align with `RankedStatKind` in src/app/interfaces/types.ts (UI
# consumers via RankedStatComponent). `births` is kept solely for the editorial chronicler — a
# cumulative stat that produces useful narrative hooks ("most prolific of his generation").
_RANKED_STATS = {
    "armor",
    "attack_speed",
    "birth_rate",
    "births",
    "critical_chance",
    "damage",
    "damage_range",
    "diplomacy",
    "health_max",
    "intelligence",
    "kills",
    "level",
    "lifespan",
    "loot",
    "mana_max",
    "money",
    "renown",
    "speed",
    "stamina_max",
    "stewardship",
    "warfare",
}


# Standard competition rank (1,2,2,4) for each stat among same-`asset_id` peers (i.e. ranks
# within the species). Only top 3 emitted — UI hides anything beyond, and the chronicler has
# no narrative use for "34th out of 114".
def _compute_ranks_in_species(actor: dict, ctx: dict, save: dict) -> dict:
    asset_id = actor.get("asset_id", "")
    cache: dict = {}
    peers = [(a["id"], _compute_stats(a, ctx, cache)) for a in save["actors_data"] if a.get("asset_id") == asset_id]
    own = next(s for aid, s in peers if aid == actor["id"])
    ranks = {}
    for stat, value in sorted(own.items()):
        if stat not in _RANKED_STATS:
            continue
        rank = sum(1 for _, s in peers if s.get(stat, 0) > value) + 1
        if rank <= 3:
            ranks[stat] = rank
    return ranks


def _equipment_rarity(modifiers: list[str]) -> str:
    max_level = max((int(m.group(1)) for m in (_LEVEL_RE.search(x) for x in modifiers) if m), default=0)
    if max_level >= 5:
        return "Legendary"
    if max_level >= 4:
        return "Epic"
    if max_level >= 3:
        return "Rare"
    return "Normal"


def _equipment_stats(asset_id: str, modifiers: list[str], item_stats: dict, mod_stats: dict) -> dict:
    out = dict(item_stats.get(asset_id, {}))
    for mod in modifiers:
        for k, v in mod_stats.get(mod, {}).items():
            out[k] = out.get(k, 0) + v
    result = {}
    for k, v in out.items():
        if isinstance(v, float):
            v = round(v, 4)
            if v.is_integer():
                v = int(v)
        if v:
            result[k] = v
    return dict(sorted(result.items()))


def _build_metadata(actor: dict, ctx: dict, save: dict) -> dict:
    sub = ctx["subspecies_by_id"].get(actor.get("subspecies")) or {}
    clan = ctx["clans_by_id"].get(actor.get("clan")) or {}
    language = ctx["languages_by_id"].get(actor.get("language")) or {}
    cities_by_id = {c["id"]: c for c in save.get("cities", [])}
    kingdoms_by_id = {k["id"]: k for k in save.get("kingdoms", [])}
    cultures_by_id = {c["id"]: c for c in save.get("cultures", [])}
    families_by_id = {f["id"]: f for f in save.get("families", [])}
    religions_by_id = {r["id"]: r for r in save.get("religions", [])}
    age_months = ctx["world_time"] - float(actor.get("created_time") or 0)
    return {
        # `age_overgrowth` (years past the actor's lifespan cap) is added on top of the natural
        # age — WB tooltips show the sum, so we mirror that to match what the chronicler sees.
        "age": round(age_months / _MONTHS_PER_YEAR) + (actor.get("age_overgrowth") or 0),
        "asset_id": actor.get("asset_id"),
        "city": (cities_by_id.get(actor.get("cityID")) or {}).get("name"),
        "clan": clan.get("name"),
        "culture": (cultures_by_id.get(actor.get("culture")) or {}).get("name"),
        "family": (families_by_id.get(actor.get("family")) or {}).get("name"),
        "favorite_food": actor.get("favorite_food"),
        "generation": int(actor.get("generation") or 1),
        "kingdom": (kingdoms_by_id.get(actor.get("civ_kingdom_id")) or {}).get("name"),
        "language": language.get("name"),
        "mass": _compute_mass(actor),
        "name": actor.get("name"),
        "personality": _compute_personality(actor, ctx, save),
        "religion": (religions_by_id.get(actor.get("religion")) or {}).get("name"),
        "roles": _compute_roles(actor, save),
        "sex": "female" if actor.get("sex") == 1 else "male",
        "subspecies": sub.get("name") or actor.get("subspecies"),
    }


# Active roles (king/village_leader/clan_chief/army_captain/family_alpha — can be lost) and
# historical foundations (alliance/clan/village/family founders, culture/language/religion
# creators — irrevocable). Returns a sorted list of role IDs, empty when the actor has none.
# Roles in canonical display order: active positions first (by hierarchical rank), then
# historical foundations (creators before founders). The UI iterates in this exact order.
_ROLE_ORDER = (
    "king",
    "village_leader",
    "clan_chief",
    "family_alpha",
    "army_captain",
    "culture_creator",
    "language_creator",
    "religion_creator",
    "alliance_founder",
    "clan_founder",
    "village_founder",
    "family_founder",
)


def _compute_roles(actor: dict, save: dict) -> list[str]:
    actor_id = actor.get("id")
    checks = {
        "alliance_founder": any(a.get("founder_actor_id") == actor_id for a in save.get("alliances", [])),
        "army_captain": any(army.get("id_captain") == actor_id for army in save.get("armies", [])),
        "clan_chief": any(c.get("chief_id") == actor_id for c in save.get("clans", [])),
        "clan_founder": any(c.get("founder_actor_id") == actor_id for c in save.get("clans", [])),
        "culture_creator": any(c.get("creator_id") == actor_id for c in save.get("cultures", [])),
        "family_alpha": any(f.get("alpha_id") == actor_id for f in save.get("families", [])),
        "family_founder": any(f.get("main_founder_id_1") == actor_id or f.get("main_founder_id_2") == actor_id for f in save.get("families", [])),
        "king": any(k.get("kingID") == actor_id for k in save.get("kingdoms", [])),
        "language_creator": any(lang.get("creator_id") == actor_id for lang in save.get("languages", [])),
        "religion_creator": any(r.get("creator_id") == actor_id for r in save.get("religions", [])),
        "village_founder": any(c.get("founder_id") == actor_id for c in save.get("cities", [])),
        "village_leader": any(c.get("leaderID") == actor_id for c in save.get("cities", [])),
    }
    return [role for role in _ROLE_ORDER if checks[role]]


# Reproduces `Actor.getMassKG` from the WB DLL: mass = (target_scale / 0.1) × mass_2 × (1 + Σ multiplier_mass).
# `target_scale` and `mass_2` aren't persisted in the save — we rebuild them from asset_id + saved_traits.
# Mass deltas applied by traits are the only ones found in the DLL (`fat`, `giant`, `tiny`, `agile`).
_MASS_BASE = {"dwarf": 75, "elf": 25, "humanoid": 65, "orc": 85}
_TRAIT_MASS_MODS = {
    "agile": {"scale": -0.01},
    "fat": {"multiplier_mass": 0.30, "scale": 0.02},
    "giant": {"scale": 0.05},
    "tiny": {"scale": -0.02},
}


def _compute_mass(actor: dict) -> int | None:
    base = _MASS_BASE.get(actor.get("asset_id") or "")
    if base is None:
        return None
    scale, mult_mass = 0.10, 0.0
    for trait in actor.get("saved_traits") or []:
        mods = _TRAIT_MASS_MODS.get(trait, {})
        scale += mods.get("scale", 0)
        mult_mass += mods.get("multiplier_mass", 0)
    return int((scale / 0.1) * base * (1 + mult_mass))


# Reproduces `Actor.updateStats` personality selection from the WB DLL: only city leaders and
# kings get a personality, picked among diplomat/administrator/militarist/balanced based on
# aggregated diplomacy/stewardship/warfare stats. `wildcard` is defined but never selected here.
def _compute_personality(actor: dict, ctx: dict, save: dict) -> str | None:
    roles = _compute_roles(actor, save)
    if "king" not in roles and "village_leader" not in roles:
        return None
    snap = _compute_stats(actor, ctx)
    diplo, stew, war = snap.get("diplomacy", 0), snap.get("stewardship", 0), snap.get("warfare", 0)
    p, max_val = "balanced", diplo
    if diplo > stew:
        p, max_val = "diplomat", diplo
    elif diplo < stew:
        p, max_val = "administrator", stew
    if war > max_val:
        p = "militarist"
    return p


def _build_inventory(actor: dict) -> dict:
    items = ((actor.get("inventory") or {}).get("dict") or {}).items()
    return dict(sorted((iid, entry.get("amount", 0)) for iid, entry in items))


def _build_companion(actor: dict, ctx: dict, save: dict, id_field: str) -> dict | None:
    companion_id = actor.get(id_field)
    if companion_id is None:
        return None
    companion = next((a for a in save["actors_data"] if a.get("id") == companion_id), None)
    if companion is None:
        return None
    snap = _compute_stats(companion, ctx)
    age_months = ctx["world_time"] - float(companion.get("created_time") or 0)
    return {
        "age": round(age_months / _MONTHS_PER_YEAR) + (companion.get("age_overgrowth") or 0),
        "health_max": snap.get("health_max", 0),
        "id": companion_id,
        "level": snap.get("level", 0),
        "money": snap.get("money", 0),
        "name": companion.get("name"),
        "renown": snap.get("renown", 0),
        "sex": "female" if companion.get("sex") == 1 else "male",
    }


# Plot the actor is currently driving — `actor.plot` points into `save.plots`. Returns `None`
# if the actor isn't involved in any plot (most actors). Targets resolved to kingdom/alliance names.
def _build_plot(actor: dict, save: dict) -> dict | None:
    plot_id = actor.get("plot")
    if plot_id is None:
        return None
    plot = next((p for p in save.get("plots", []) if p.get("id") == plot_id), None)
    if plot is None:
        return None
    kingdoms_by_id = {k["id"]: k for k in save.get("kingdoms", [])}
    alliances_by_id = {a["id"]: a for a in save.get("alliances", [])}
    return {
        "name": plot.get("name"),
        "progress": round(float(plot.get("progress_current", 0)), 1),
        "started_at": round(float(plot.get("created_time", 0)), 2),
        "target_alliance": (alliances_by_id.get(plot.get("id_target_alliance")) or {}).get("name"),
        "target_kingdom": (kingdoms_by_id.get(plot.get("id_target_kingdom")) or {}).get("name"),
        "type_id": plot.get("plot_type_id"),
    }


def _build_trait_list(trait_ids: list[str], traits_data: dict, narrative: bool) -> list:
    out = []
    for tid in trait_ids or []:
        entry = traits_data.get(tid) or {}
        item: dict = {"id": tid, "stats": entry.get("stats") or {}}
        if narrative:
            for k in ("description", "flavor", "rarity"):
                if k in entry:
                    item[k] = entry[k]
        out.append(dict(sorted(item.items())))
    return sorted(out, key=lambda t: t["id"])


def _build_equipment_list(actor: dict, ctx: dict) -> list:
    item_stats = ctx["equipment"]["items"]
    mod_stats = ctx["equipment"]["modifiers"]
    world_time = ctx["world_time"]
    out = []
    for iid in actor.get("saved_items") or []:
        item = ctx["items_by_id"].get(iid)
        if item is None:
            continue
        mods = item.get("modifiers") or []
        ct = item.get("created_time")
        out.append(
            {
                "age": round((world_time - ct) / _MONTHS_PER_YEAR) if ct is not None else None,
                "asset_id": item["asset_id"],
                "by": item.get("by"),
                "durability": item.get("durability"),
                "from": item.get("from"),
                "id": iid,
                "kills": item.get("kills", 0),
                "modifiers": sorted(mods),
                "rarity": _equipment_rarity(mods),
                "stats": _equipment_stats(item["asset_id"], mods, item_stats, mod_stats),
            }
        )
    return sorted(out, key=lambda i: i["id"])


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: overview.py <id> [sections] — see tools/tools.md", file=sys.stderr)
        return 2
    try:
        actor_id = int(argv[0])
    except ValueError:
        print(f"invalid id: {argv[0]}", file=sys.stderr)
        return 1
    try:
        sections = parse_sections(argv[1] if len(argv) > 1 else None, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not CURRENT_SAVE.exists():
        print(f"no save found at {CURRENT_SAVE}", file=sys.stderr)
        return 2
    save = load_save()
    actor = next((a for a in save["actors_data"] if a.get("id") == actor_id), None)
    if actor is None:
        print(f"unknown actor: {actor_id}", file=sys.stderr)
        return 1
    ctx = _build_context(save)
    sub = ctx["subspecies_by_id"].get(actor.get("subspecies"))
    if sub is None:
        print(f"no subspecies for actor {actor_id}", file=sys.stderr)
        return 1

    out: dict = {}
    if "best_friend" in sections:
        out["best_friend"] = _build_companion(actor, ctx, save, "best_friend_id")
    if "creature_traits" in sections:
        out["creature_traits"] = _build_trait_list(actor.get("saved_traits") or [], ctx["creature_traits"], narrative=True)
    if "equipment" in sections:
        out["equipment"] = _build_equipment_list(actor, ctx)
    if "inventory" in sections:
        out["inventory"] = _build_inventory(actor)
    if "lover" in sections:
        out["lover"] = _build_companion(actor, ctx, save, "lover")
    if "metadata" in sections:
        out["metadata"] = _build_metadata(actor, ctx, save)
    if "plot" in sections:
        out["plot"] = _build_plot(actor, save)
    if "ranks_in_species" in sections:
        out["ranks_in_species"] = _compute_ranks_in_species(actor, ctx, save)
    if "stats" in sections:
        out["stats"] = _compute_stats(actor, ctx, save)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

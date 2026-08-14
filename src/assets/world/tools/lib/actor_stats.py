# Shared actor stats pipeline — mirrors `Actor.updateStats` from WB's `Assembly-CSharp.dll`.
#
# ─── Maintenance / algorithm reference ───
# Full algorithm spec: `chronicler.md § VI`. Numeric tables (_GENE_VALUES, _GENE_INDEX, ceil-on-bad, synergy-always) come from it + WorldBox's in-game tooltips.
#
# Pipeline per chromosome:
#   1. For each locus (skipping `void_loci`):
#        a. Detect BAD: at least one cardinal neighbor (N/S/E/W) contains the `bad` gene.
#        b. Detect GOLDEN: every side that holds a real gene synergizes (≥1 such side). Borders AND `empty` slots are skipped. BAD wins over GOLDEN.
#        c. Apply tier: BAD → floor(v/2) (ceil for `attack_speed`/`damage_1`/`health_1`/`speed_1`); GOLDEN → v×2; else v as-is.
#        d. Accumulate per stat name — into the neutral block, or into one sex's block for the neighbours of a `bonus_male`/`bonus_female` locus.
#   2. Actor-side: neutral block + the actor's sex block, then traits, equipment, level, `normalize`, derived stats, multipliers, `normalize` again.
#   3. `_cleanup_stats` truncates floats toward zero (1 decimal for `_KEEP_DECIMAL`), renames, drops zeros.
#
# Color synergy: .NET `System.Random` (seed `life_dna + gene._GENE_INDEX`) → 4-side color signature/gene; int32 overflow mirrored (`_to_int32()`/`_SystemRandom`).
# Color positions (per chronicler.md): indices target *spaced* text (`"XXX XXX XXX XXX XXX"`, 19 chars) at 0/8/10/18 → unspaced 15-char text at 0/6/8/14.
# ⚠️ If you ever rewrite the DNA generator to keep the spaces, shift the indices back.

import math
from collections import Counter
from functools import cache
from math import inf

from shared import (
    HAPPY_MIN_HAPPINESS,
    NON_FOOD_SPECIES,
    PROFESSION_KING,
    PROFESSION_LEADER,
    PROFESSION_WARRIOR,
    SATED_MIN_NUTRITION,
    SICK_TRAITS,
    UNHAPPY_MAX_HAPPINESS,
    UNITS_PER_YEAR,
    actor_age,
    age_thresholds,
    has_emotions,
    head_money,
    index_by_id,
    life_stage,
    load_data,
    sex_label,
)

# Genes that round UP on BAD (instead of down).
_CEIL_ON_BAD = {"attack_speed", "damage_1", "health_1", "speed_1"}

_COLOR_MAP = {"A": "green", "C": "blue", "G": "yellow", "T": "red"}  # in the order of the `"ACGT"` literal that indexes it
_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# Stats dropped from output — not consumed by chronicler UI or fixtures. Add new stats here when entering the pipeline but not surfaced (see chapter.interface.ts).
_DROP = {"accuracy", "critical_damage_multiplier", "knockback", "loyalty_traits", "mass", "mass_2", "range", "targets"}

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

_GRID_COLS = 6

# Stats kept as 1-decimal floats — integer truncate would lose meaningful precision (damage_range is typically `damage × ratio` where ratio < 1).
_KEEP_DECIMAL = {"damage_range"}

# Per `SimGlobalAsset.ctor` IL → static level_mod_bonus_* / _MANA_PER_INTELLIGENCE constants.
_LEVEL_MOD = {"health": 0.05, "mana": 0.02, "stamina": 0.02}
_LEVEL_VETERAN_SKILL_BONUS = 0.1
_LEVEL_VETERAN_THRESHOLD = 5
_MANA_PER_INTELLIGENCE = 10
_META_RATIOS = ("children", "happy", "homeless", "unhappy")  # WB `IMetaObject`'s four, named as its getters are — every one of them a share of the living.


# WB `BaseStatAsset.normalize_min`/`normalize_max` for the 23 bounded stats — an unset max (2^31) is `inf`. Floors bite: traits push under, WB lifts back.
_NORMALIZE = {
    "accuracy": (1, 10),
    "armor": (0, 99),
    "army": (0.1, inf),
    "attack_speed": (0.5, 10),
    "bonus_towers": (0, 2),
    "construction_speed": (1, 100),
    "damage": (1, inf),
    "damage_range": (0.1, inf),
    "diplomacy": (0, 999),
    "health": (1, inf),
    "intelligence": (0, 999),
    "lifespan": (1, inf),
    "offspring": (0, 1000),
    "personality_administration": (0, 1),
    "personality_aggression": (0, 1),
    "personality_diplomatic": (0, 1),
    "personality_rationality": (0, 1),
    "projectiles": (1, inf),
    "speed": (1, inf),
    "stamina": (1, inf),
    "stewardship": (0, 999),
    "throwing_range": (1, 100),
    "warfare": (0, 999),
}

_OPPOSITE = {(1, 0): "left", (-1, 0): "right", (0, 1): "up", (0, -1): "down"}
_RENAMES = {"cities": "max_cities", "health": "health_max", "mana": "mana_max", "offspring": "max_children", "stamina": "stamina_max"}
_SEX_GENES = {"bonus_female": "female", "bonus_male": "male"}  # `GeneAsset.is_bonus_male`/`is_bonus_female` — the block each one feeds.
_SIDE = {(1, 0): "right", (-1, 0): "left", (0, 1): "down", (0, -1): "up"}
_SYNERGY_ALWAYS = {"bonus_female", "bonus_male", "mutagenic"}


def _add_chromosome_stats(totals: dict, sub: dict, life_dna: int) -> dict:
    sex_bonus: dict[str, dict] = {"female": {}, "male": {}}
    for chrom in sub.get("saved_chromosome_data") or []:
        loci = chrom.get("loci") or []
        void_set = set(chrom.get("void_loci") or [])
        super_set = set(chrom.get("super_loci") or [])
        for idx, gene in enumerate(loci):
            if idx in void_set:
                continue
            if sex := _SEX_GENES.get(gene):  # carries no stat of its own — it makes its neighbours pay a second time, into one sex's block
                _add_sex_bonus(sex_bonus[sex], loci, idx, void_set, super_set, life_dna)
                continue
            entry = _GENE_VALUES.get(gene)
            if entry is None:
                continue
            stat, value = entry
            bad = _is_bad(loci, idx)
            golden = (not bad) and _is_golden(loci, idx, void_set, super_set, life_dna)
            totals[stat] = totals.get(stat, 0) + _apply_tier(gene, value, bad, golden)
    return sex_bonus


# Civil progression accumulator (`actor.custom_data_float`) — diplomacy/warfare/stewardship/intelligence +1 per conversation/event/aging tick over actor's life.
def _add_custom_data_float(totals: dict, custom: dict | None) -> None:
    for k, v in (custom or {}).items():
        totals[k] = totals.get(k, 0) + v


def _add_equipment_stats(totals: dict, item_ids: list[int], items_by_id: dict, item_stats: dict, mod_stats: dict) -> None:
    for iid in item_ids or []:
        item = items_by_id.get(iid)
        if item is None:
            continue
        for k, v in ((item_stats.get(item["asset_id"]) or {}).get("stats") or {}).items():
            totals[k] = totals.get(k, 0) + v
        for mod in item.get("modifiers") or []:
            for k, v in (mod_stats.get(mod) or {}).items():
                totals[k] = totals.get(k, 0) + v


# WB `Chromosome.combineBonusesForSides`: the four cardinal neighbours of a sex-bonus locus pay into that sex block at their neutral value, halved next to a `bad`.
def _add_sex_bonus(block: dict, loci: list[str], idx: int, void_set: set[int], super_set: set[int], life_dna: int) -> None:
    gathered: dict = {}
    for dx, dy in _DIRECTIONS:
        ngene, nidx = _neighbor(loci, void_set, idx, dx, dy)
        if ngene is None or (entry := _GENE_VALUES.get(ngene)) is None:
            continue
        stat, value = entry
        bad = _is_bad(loci, nidx)
        golden = (not bad) and _is_golden(loci, nidx, void_set, super_set, life_dna)
        gathered[stat] = gathered.get(stat, 0) + _apply_tier(ngene, value, bad, golden)
    crippled = _is_bad(loci, idx)
    for stat, value in gathered.items():
        block[stat] = block.get(stat, 0) + (_half(value) if crippled else value)


def _add_species_stats(totals: dict, asset_id: str, species_data: dict) -> None:
    for k, v in ((species_data.get(asset_id) or {}).get("stats") or {}).items():
        totals[k] = totals.get(k, 0) + v


def _add_trait_stats(totals: dict, trait_ids: list[str], traits_data: dict) -> None:
    for trait_id in trait_ids or []:
        entry = traits_data.get(trait_id) or {}
        for k, v in (entry.get("stats") or {}).items():
            totals[k] = totals.get(k, 0) + v


# WB `Subspecies.calculateAgeRelatedStats` reads the biology's own lifespan, not its bearer's — so the threshold is cached per biology, as WB caches it.
def _age_adult(actor: dict, ctx: dict, base_cache: dict, memo: dict) -> float:
    sub_id = actor.get("subspecies")
    if sub_id not in memo:
        actor_stat_totals(actor, ctx, base_cache, lifespan_only=True)  # fills `base_cache`; the base is species + chromosomes + the biology's own traits
        base = (base_cache.get(sub_id) or ({}, {}))[0]
        memo[sub_id] = age_thresholds(int(base.get("lifespan") or 0))[0]
    return memo[sub_id]


# Per `Actor.updateStats` + tooltip: damage += warfare/5; damage_range → raw-hp amplitude (int(damage*damage_range)); critical_chance → percent (0.28 → 28).
def _apply_damage_finalize(totals: dict) -> None:
    if "damage" in totals:
        totals["damage"] = totals["damage"] + totals.get("warfare", 0) / 5
    if "damage_range" in totals:
        totals["damage_range"] = totals.get("damage", 0) * totals["damage_range"]
    if "critical_chance" in totals:
        totals["critical_chance"] = totals["critical_chance"] * 100


# The three stats `updateStats` derives right after normalize #1, in WB's order: each truncates a clamped source like C#'s `(int)`, so `//` is safe.
def _apply_derived_stats(totals: dict) -> None:
    totals["cities"] = totals.get("cities", 0) + int(totals.get("stewardship", 0)) // 6 + 1  # one more holding a steward can hold together per 6 points
    if towers := int(totals.get("warfare", 0) / 10):
        totals["bonus_towers"] = totals.get("bonus_towers", 0) + towers
    if intel := totals.get("intelligence", 0):
        totals["mana"] = totals.get("mana", 0) + int(intel * _MANA_PER_INTELLIGENCE)


# Apply Actor.updateStats end-of-method level scaling: stat *= (1 + level × mult), and a flat +0.1 to skill_combat / skill_spell when level > 5.
def _apply_level_scaling(totals: dict, level: int) -> None:
    for stat, mult in _LEVEL_MOD.items():
        if stat in totals:
            totals[stat] = totals[stat] * (1 + level * mult)
    if level > _LEVEL_VETERAN_THRESHOLD:
        for stat in ("skill_combat", "skill_spell"):
            totals[stat] = totals.get(stat, 0) + _LEVEL_VETERAN_SKILL_BONUS


# Resolve every `multiplier_X` key as a coefficient on stats[X]: `final = base × (1 + multiplier)`.
def _apply_multipliers(totals: dict) -> None:
    for k in [k for k in totals if k.startswith("multiplier_")]:
        target = k.removeprefix("multiplier_")
        if target in totals:
            totals[target] *= 1 + totals[k]
        del totals[k]


# Per `Actor.calculateOffspringBasedOnAge`: scale `offspring` by an age-bracket multiplier to match the in-game tooltip (e.g. raw 3 → 2 for a mature actor).
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


# BAD → floor(v/2) (or ceil for the few `_1`-tier genes listed in _CEIL_ON_BAD); GOLDEN → v×2.
def _apply_tier(gene: str, value: float, bad: bool, golden: bool) -> float:
    if bad:
        return -(-value // 2) if gene in _CEIL_ON_BAD else value // 2
    return value * 2 if golden else value


# Truncate toward zero like C#'s `(int)`, not floor — negatives occur. `health`/`mana` => `health_max`/`mana_max`: post-pipeline maximums.
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


# Returns {left, up, down, right} colors for a gene's DNA strand. Memoized: each gene's colors only depend on (gene, life_dna), and life_dna is constant per run.
@cache
def _gene_colors(gene: str, life_dna: int) -> dict:
    idx = _GENE_INDEX.get(gene)
    if idx is None:
        return {}
    rnd = _SystemRandom(_to_int32(life_dna + idx))
    text = "".join("ACGT"[rnd.Next(4)] for _ in range(15))
    return {"left": _COLOR_MAP[text[0]], "up": _COLOR_MAP[text[6]], "down": _COLOR_MAP[text[8]], "right": _COLOR_MAP[text[14]]}


# WB `GeneAsset.getHalfStats`: a whole number floors on halving, a fractional one just keeps its remainder.
def _half(value: float) -> float:
    return math.floor(value * 0.5) if float(value).is_integer() else value * 0.5


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
        # An empty slot reads as a border, not a side that failed — WB shows the same `Guérilla I` at +2 beside an empty and +1 beside a real gene.
        if ngene is None or ngene == "empty":
            continue
        non_border += 1
        if _synergizes(gene, ngene, dx, dy, super_set, idx, nidx, life_dna):
            synergized += 1
    return synergized >= 1 and synergized == non_border


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


# WB `BaseStats.normalize` — bounded stats clamped, absent left absent. Driven by `_NORMALIZE`, not `totals`: measured faster, half an actor's stats are bounded.
def _normalize(totals: dict) -> None:
    for stat, (low, high) in _NORMALIZE.items():
        if stat in totals:
            totals[stat] = min(max(totals[stat], low), high)


def _synergizes(gene: str, ngene: str, dx: int, dy: int, super_set: set[int], my_idx: int, n_idx: int, life_dna: int) -> bool:
    my_super = my_idx in super_set
    n_super = n_idx in super_set
    if my_super and n_super:
        return False  # two amplifiers don't synergize with each other
    if my_super or n_super:
        return True  # amplifier synergizes with anything non-empty
    if gene in _SYNERGY_ALWAYS or ngene in _SYNERGY_ALWAYS:
        return True
    return _gene_colors(gene, life_dna).get(_SIDE[dx, dy]) == _gene_colors(ngene, life_dna).get(_OPPOSITE[dx, dy])


# Faithful port of .NET `System.Random` (subtractive generator). Constants and seed loop match the .NET reference — do not "simplify" without verifying outputs.
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

    def Next(self, mv: int) -> int:
        return int((self._internal_sample() / self.MBIG) * mv)

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


# Mirrors C# int32 wrap-around — required because the game's SystemRandom relies on it.
def _to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x >= 0x80000000 else x


# WB's `Actor.stats`, floats intact, before `_cleanup_stats`. Combine stats from here: WB adds first, truncates once, so 14.5 stays 14.5.
def actor_stat_totals(actor: dict, ctx: dict, subspecies_base_cache: dict | None = None, *, lifespan_only: bool = False) -> dict:
    sub_id = actor.get("subspecies")
    sub = ctx["subspecies_by_id"].get(sub_id) if sub_id is not None else None
    if sub is None:
        return {}
    cached = subspecies_base_cache.get(sub_id) if subspecies_base_cache is not None else None
    if cached is None:
        base = {}
        _add_species_stats(base, actor.get("asset_id", ""), ctx["species_data"])
        sex_bonus = _add_chromosome_stats(base, sub, ctx["life_dna"])
        _add_trait_stats(base, sub.get("saved_traits") or [], ctx["subspecies_traits"])
        cached = (base, sex_bonus)
        if subspecies_base_cache is not None:
            subspecies_base_cache[sub_id] = cached
    base, sex_bonus = cached
    totals = dict(base)
    for stat, value in sex_bonus[sex_label(actor)].items():  # `updateStats` merges `base_stats_male`/`base_stats_female` on top of the neutral block
        totals[stat] = totals.get(stat, 0) + value
    _add_trait_stats(totals, actor.get("saved_traits") or [], ctx["creature_traits"])
    _add_trait_stats(totals, (ctx["clans_by_id"].get(actor.get("clan")) or {}).get("saved_traits") or [], ctx["clan_traits"])
    _add_trait_stats(totals, (ctx["languages_by_id"].get(actor.get("language")) or {}).get("saved_traits") or [], ctx["language_traits"])
    # Nothing below writes `lifespan` — equipment grants it on none of its 20 stats, level scales three others, the rest only read it. Measured 41 % cheaper.
    if lifespan_only:
        _normalize(totals)
        _apply_multipliers(totals)
        return totals
    _add_equipment_stats(totals, actor.get("saved_items") or [], ctx["items_by_id"], ctx["equipment"]["items"], ctx["equipment"]["modifiers"])
    _add_custom_data_float(totals, actor.get("custom_data_float"))
    _apply_level_scaling(totals, max(int(actor.get("level") or 0), 1))  # WB scaling starts at level 1 even when the raw save field is absent / 0 (matches tooltip).
    _normalize(totals)  # `updateStats` normalizes here, ahead of the derived stats: mana reads the clamped intelligence, damage the clamped warfare.
    _apply_derived_stats(totals)
    _apply_multipliers(totals)
    _apply_damage_finalize(totals)
    _normalize(totals)  # and again at the very end, once the multipliers have had their say
    age_units = ctx["world_time"] - float(actor.get("created_time") or 0)
    lifespan_units = totals.get("lifespan", 0) * UNITS_PER_YEAR
    _apply_offspring_age_scaling(totals, age_units / lifespan_units if lifespan_units else 0)
    return totals


# Shared context built from one save load — feeds every actor stats computation. Callers (actor/info.py, kingdom/info.py) typically extend it with their keys.
def build_actor_stats_context(save: dict) -> dict:
    return {
        "clan_traits": load_data("clan-traits.json"),
        "clans_by_id": index_by_id(save.get("clans", [])),
        "creature_traits": load_data("creature-traits.json"),
        "equipment": load_data("equipment.json"),
        "items_by_id": index_by_id(save["items"]),
        "language_traits": load_data("language-traits.json"),
        "languages_by_id": index_by_id(save.get("languages", [])),
        "life_dna": int(save["mapStats"].get("life_dna") or 0),
        "species_data": load_data("species.json"),
        "subspecies_by_id": index_by_id(save.get("subspecies", [])),
        "subspecies_traits": load_data("subspecies-traits.json"),
        "world_time": float(save["mapStats"].get("world_time") or 0),
    }


# Aggregate one actor's stats (no counters). `subspecies_base_cache` reuses the species+chromosomes+traits base per subspecies — ~7× speedup when ranking peers.
def compute_actor_stats(actor: dict, ctx: dict, subspecies_base_cache: dict | None = None) -> dict:
    cleaned = _cleanup_stats(actor_stat_totals(actor, ctx, subspecies_base_cache))
    # Two stats WB reads off a single office-holder: `max_cities` from a king (`Kingdom.getMaxCities`), `bonus_towers` from a city leader (its watch-tower cap).
    for stat, holder in (("bonus_towers", PROFESSION_LEADER), ("max_cities", PROFESSION_KING)):
        if actor.get("profession") != holder:
            cleaned.pop(stat, None)
    return cleaned


# WB `IMetaObject`'s four ratios, the input its self-report reads. Happiness only answers for a biology bearing an `amygdala`, WB's own `has_emotions` tag.
def meta_ratios(actors: list[dict], ctx: dict) -> dict:
    if not (total := len(actors)):
        return dict.fromkeys(_META_RATIOS, 0.0)
    base_cache: dict = ctx.setdefault("subspecies_base_cache", {})
    counts: Counter[str] = Counter()
    memo: dict = {}
    for actor in actors:
        if has_emotions(actor, ctx["subspecies_by_id"]):  # an unfeeling soul still counts in the whole, as WB divides by every unit it holds
            happiness = int(actor.get("happiness") or 0)
            counts["happy"] += happiness >= HAPPY_MIN_HAPPINESS
            counts["unhappy"] += happiness < UNHAPPY_MAX_HAPPINESS
        # WB `calcIsBaby`: a child is a soul below its biology's `age_adult`, and only where its species was given a baby form — most creatures never have one.
        if (ctx["species_data"].get(actor.get("asset_id")) or {}).get("baby_form"):
            counts["children"] += actor_age(actor, ctx["world_time"]) < _age_adult(actor, ctx, base_cache, memo)
        counts["homeless"] += not actor.get("homeBuildingID")
    return {key: counts[key] / total for key in _META_RATIOS}


# What a body's members tell about it — age tiers, sexes, mutual couples, the tallies each soul answers for alone. `settlement_population` adds stores and head.
def population_of(actors: list[dict], ctx: dict) -> dict:
    base_cache: dict = ctx.setdefault("subspecies_base_cache", {})  # created here too: a caller may ask for this block alone, before anything else fills it
    by_id, ids = ctx["actors_by_id"], {a["id"] for a in actors}
    counts: Counter[str] = Counter()
    paired: set[int] = set()
    stages: Counter[str] = Counter()
    world_time = ctx["world_time"]
    for a in actors:
        age = int((world_time - float(a.get("created_time") or 0)) / UNITS_PER_YEAR) + (a.get("age_overgrowth") or 0)
        # Raw totals, and equipment skipped: only `lifespan` is read, so neither the cleanup's rename-and-sort nor the item walk earns its keep here.
        lifespan = int(actor_stat_totals(a, ctx, base_cache, lifespan_only=True).get("lifespan", 0))
        stages[life_stage(age, age_thresholds(lifespan)[0], lifespan)] += 1
        counts["men"] += a.get("sex") != 1
        counts["money"] += int(a.get("money") or 0)
        counts["renown"] += int(a.get("renown") or 0)
        counts["warriors"] += a.get("profession") == PROFESSION_WARRIOR
        counts["homeless"] += not a.get("homeBuildingID")
        counts["familyless"] += not a.get("family")
        counts["happy"] += int(a.get("happiness") or 0) >= HAPPY_MIN_HAPPINESS and has_emotions(a, ctx["subspecies_by_id"])
        if (a.get("asset_id") or "") not in NON_FOOD_SPECIES:  # WB `needsFood`: undead have no diet, so they never weigh on the hunger share
            counts["eaters"] += 1
            counts["fed"] += int(a.get("nutrition") or 0) >= SATED_MIN_NUTRITION
        traits = a.get("saved_traits") or []
        counts["immortals"] += "immortal" in traits
        counts["infected"] += "infected" in traits
        counts["sick"] += not SICK_TRAITS.isdisjoint(traits)
        lover = a.get("lover")
        if lover is not None and lover in ids and a["id"] not in paired and by_id.get(lover, {}).get("lover") == a["id"]:
            counts["couples"] += 1
            paired.update((a["id"], lover))
    total = len(actors)
    return {
        "adults": stages["adult"],
        "babies": stages["baby"],
        "children": stages["child"],
        "couples": counts["couples"],
        "elders": stages["elder"],
        "familyless": counts["familyless"],
        "fed_pct": round(100 * counts["fed"] / eaters) if (eaters := counts["eaters"]) else 0,  # share of the food-needing sated (nutrition ≥ 60)
        "happy": counts["happy"],
        "housed_pct": round((total - counts["homeless"]) / total * 100) if total else 0,
        **({"immortals": n} if (n := counts["immortals"]) else {}),
        **({"infected": n} if (n := counts["infected"]) else {}),
        "men": counts["men"],
        "money": counts["money"],  # every coin the living carry between them
        "renown_total": counts["renown"],  # summed renown of the members, distinct from whatever the body itself is worth
        **({"sick": n} if (n := counts["sick"]) else {}),
        "teens": stages["teen"],
        "total": total,
        "warriors": counts["warriors"],
        "women": total - counts["men"],
    }


# The population panel both tiers print, field for field — `tier` picks the ctx tallies, as `settlement_rank_getters` does. `immortals`/`infected`/`sick` drop at 0.
def settlement_population(entity: dict, ctx: dict, tier: str) -> dict:
    entity_id = entity["id"]

    def tally(name: str) -> int:
        return ctx[f"{name}_by_{tier}"][entity_id]

    population = population_of(ctx[f"actors_by_{tier}"].get(entity_id, []), ctx)
    money, nobles_money, total = population["money"], tally("nobles_money"), population["total"]

    # What a roof over stores and a head on the throne add to what the people alone say — a biology or a band has neither, and reads `population_of` bare.
    return dict(
        sorted(
            {
                **population,
                "food_per_capita": round(tally("food") / total, 1) if total else 0,  # eatable stock ÷ population — food security
                "nobles": tally("nobles"),
                "nobles_money": nobles_money,  # the other nobles' coins, the head excluded — his own purse sits in `metadata`
                "subjects_money": money - head_money(entity, ctx, tier) - nobles_money,  # commoners' coins: `money` less the head and the nobility
                "wealth_per_capita": round((money + tally("gold")) / total, 1) if total else 0,  # `metadata.wealth` ÷ population
            }.items()
        )
    )

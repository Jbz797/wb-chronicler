#!/usr/bin/env python3

# One subspecies: the biology a lineage of actors was born into, its sworn traits and who still carries it. User-facing docs: `docs/tools.md`.
# WB mutates one out of another as a world ages, so a species holds many — and a subspecies outlives every crown and clan its bearers ever joined.

import sys
from argparse import ArgumentTypeError
from collections import Counter, defaultdict
from functools import cache, partial
from operator import itemgetter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from roster import ISLET, LIMIT, WATER, make_room, one_kind, refused, roll, roster_call, stands_on, told_part

from actor_stats import (
    breeding_age,
    build_actor_stats_context,
    compute_actor_stats,
    crossed_at,
    is_hungry,
    maturation_months,
    meta_ratios,
    pop_of,
    status_left,
    subspecies_stats,
)
from grid import LazyTileGrid
from islands import TileIslands, compute_islands_cached
from shared import (
    MIN_PER_CAPITA_UNITS,
    NEW_BABY_NUTRITION,
    PROFESSION_WARRIOR,
    SAVES_DIR,
    UNITS_PER_MONTH,
    absent_entity,
    actor_xy,
    arg_parser,
    asset_families,
    asset_kinds,
    biome_lore,
    breeding_mode,
    build_trait_ids,
    build_trait_list,
    children_by_id,
    competition_ranks,
    death_causes,
    emit,
    entity_age,
    entity_born,
    hand_usage,
    index_by_id,
    is_boat,
    is_sapient,
    kept_deaths,
    light,
    limit_arg,
    load_data,
    load_save,
    meta_report,
    needs_food,
    parse_sections,
    passed_unseen,
    population_breakdown,
    run,
    sections_arg,
    settlement_leaders,
    sex_label,
    since_saves,
    spores_unfed,
    take_chapter,
    take_since,
    unsited_reason,
    walk_tiles,
    world_date,
    world_laws,
)
from walking import WalkMap, walk_way

_ALL_SECTIONS = ("breakdown", "leaders", "metadata", "pop", "ranks", "species", "stats", "taxonomy", "traits")
_CARRYING = ("pregnant", "pregnant_parthenogenesis")  # WB's two statuses that end on a birth
_EMPTY_SPECIES = {"cities": 0, "kingdoms": 0, "pop": 0, "renown": 0, "subspecies": 0}  # What a species is ranked on; its keys double as the rank getters.
_GIVES_WAY = ("biome", "born", "members", "asset_id")  # what a field `--with` adds takes the place of, least telling first: the sheet keeps them
_GOOD_ISLET = 5  # WB `TileIsland.isGoodIslandForActor`: an islet of so few tiles is one a body leaves before anything else, breeding included
_MINDS = ("beasts", "sapient")  # what `--filter` splits the lineages by, beside `type:<kind>`
_NEEDS_ACTORS = frozenset({"breakdown", "leaders", "metadata", "pop", "ranks"})  # the rest read the subspecies record and its libraries
_PARTS = ("arrived", "came_and_went", "died")  # what a `--since` roll files a lineage under, each a `--filter` word too
_SEXED = "reproduction_sexual"  # the one breeding WB pairs by opposite sexes: a hermaphrodite takes any partner of its kind
_SOULBORNE = "reproduction_soulborne"  # a lineage born of the souls it strikes: `action_attack_target` harvests one off a body that `has_soul`
_STRATEGIC = frozenset({"reproduction_hermaphroditic", "reproduction_parthenogenesis", "reproduction_sexual"})  # carried only if viviparous, else laid at once
_TAXONOMY_RANKS = ("kingdom", "phylum", "class", "order", "family", "genus")  # WB's own order, broadest first — `render` keeps it, not alphabetical.
_UNCARRIED = frozenset({"reproduction_fission", "reproduction_spores"})  # WB makes the new body there and then, `maturation` never read


# What bars a pair, the bodies one cause holds told after it once: `hungry 425 426`, a world law alone.
def _bars_told(barred: list[str]) -> list[str]:
    by_cause: dict[str, list[str]] = {}
    for bar in barred:
        cause, _, body = bar.rpartition(" ")
        by_cause.setdefault(cause if body.isdigit() else bar, []).extend([body] if body.isdigit() else [])
    return [" ".join([cause, *bodies]) for cause, bodies in by_cause.items()]


# How a lineage breeds, WB's trait ids prefixes off — `sexual, viviparity` —, `none` where no mode leads it to a birth: `--with reproduction`.
def _breeding(lineage: dict) -> str:
    own = (trait for trait in sorted(lineage.get("saved_traits") or ()) if trait.startswith("reproduction_"))
    return ", ".join(trait.removeprefix("reproduction_").removeprefix("strategy_") for trait in own) or "none"


# What keeps a body of age from breeding, WB weighing each partner: a belly short of a baby or half-full, a footing to leave first — tagged `tiny_islet 40`.
def _breeding_bars(actor: dict, ctx: dict, island_of: TileIslands, grid: LazyTileGrid, names: list[str]) -> set[str]:
    bars = set()
    if needs_food(ctx["subspecies_by_id"].get(actor.get("subspecies"))) and (int(actor.get("nutrition") or 0) < NEW_BABY_NUTRITION or is_hungry(actor, ctx)):
        bars.add("hungry")
    if (here := stands_on(actor, island_of, grid, names)) == WATER:
        bars.add(WATER)
    elif here == ISLET and island_of.islet_size(actor_xy(actor)) <= _GOOD_ISLET:
        bars.add("tiny_islet")
    return {f"{bar} {actor['id']}" for bar in bars}


# Every living lineage, by id, a line each as `subspecies … metadata` tells it: its kind, name, members, the biome that shaped it, its month — `type:` narrows.
def _build_lineages(save: dict, kinds: set[str] | None, minded: bool | None, breeding: bool) -> list[dict]:
    members = Counter(actor.get("subspecies") for actor in save.get("actors_data") or [] if not is_boat(actor))
    rows = []
    for lineage in sorted(save.get("subspecies") or [], key=lambda s: s["id"]):
        if (kinds is not None and lineage.get("species_id") not in kinds) or (minded is not None and is_sapient(lineage) != minded):
            continue
        biome = (lineage.get("biome_variant") or "").removeprefix("biome_")
        rows.append(
            {
                "asset_id": lineage.get("species_id"),
                **({"biome": biome} if biome_lore(biome) else {}),
                "born": entity_born(lineage),
                "id": lineage["id"],
                "members": members[lineage["id"]],
                "name": lineage.get("name"),
                **({"reproduction": _breeding(lineage)} if breeding else {}),
                **({"sapient": True} if is_sapient(lineage) else {}),
            }
        )
    return rows


# The biology's identity card: WB's lifetime counters beside what a walk over the living tells. Every counter drops at zero — the panels read them through `?? 0`.
def _build_metadata(subspecies: dict, members: list[dict], ctx: dict) -> dict:
    biome_id = (subspecies.get("biome_variant") or "").removeprefix("biome_")
    causes = death_causes(subspecies)
    cities = {c for a in members if (c := a.get("cityID"))}
    families = {f for a in members if (f := a.get("family"))}
    island_of = ctx["island_lookup"]()
    kingdoms = {k for a in members if (k := a.get("civ_kingdom_id"))}
    # What WB has the biology say of itself
    report = meta_report("meta", {"units": len(members), **meta_ratios(members, ctx)}, (ctx["world_time"], "subspecies", subspecies["id"]))

    return {
        "age": entity_age(subspecies, ctx["world_time"]),
        **({"biome": biome_id} if biome_lore(biome_id) else {}),  # the biome that shaped the mutation, never the stock — `default_color` being none, the key drops
        **({"births": births} if (births := int(subspecies.get("total_births") or 0)) else {}),
        "born": entity_born(subspecies),  # chronicler-only: its month, where `age` counts whole years
        **({"cities": len(cities)} if cities else {}),  # settlements its bearers answer from — a biology spreads wherever its carriers walk
        **({"deaths": deaths} if (deaths := int(subspecies.get("total_deaths") or 0)) else {}),
        **({"deaths_by_cause": causes} if causes else {}),  # chronicler-only: how the biology has been dying, which its totals alone never say
        **({"families": len(families)} if families else {}),  # bloodlines carrying it — the count says whether the biology runs in one line or fans out over many
        "id": subspecies["id"],  # the block travels into `chapter.json`, detached from its command — the UI resolves the tag from this
        "islands": sorted({iid for a in members if (iid := island_of.get(actor_xy(a))) is not None}),  # 1 = biggest — presence, not weight.
        **({"kills": kills} if (kills := int(subspecies.get("total_kills") or 0)) else {}),
        **({"kingdoms": len(kingdoms)} if kingdoms else {}),  # crowns its bearers answer to — biology owes nothing to borders, so it crosses them freely
        "members": len(members),  # its living, each named by `actor --roster --filter subspecies:<id>`
        "name": subspecies.get("name"),
        **({"report": report} if report else {}),
        "sapient": is_sapient(subspecies),  # the faculty that lets its bearers found cities — a beast's biology never carries it
    }


# What the living say of the body they belong to — the settlement block less its granary and its head, and less `total`, which `metadata.members` counts.
def _build_pop(members: list[dict], ctx: dict) -> dict:
    return {key: value for key, value in pop_of(members, ctx).items() if key != "total"}


# The stock's standing over every soul of that species, and its next birth: counts flat beside its `ranks`, `id` to say whose — `chapter.json` keeps the counts.
def _build_species(subspecies: dict, save: dict, ctx: dict, *, detailed: bool) -> dict:
    asset_id = subspecies.get("species_id") or ""
    totals = _species_totals(save)
    own = totals.get(asset_id) or _EMPTY_SPECIES.copy()
    ranks = competition_ranks(own, list(totals.values()), {key: itemgetter(key) for key in _EMPTY_SPECIES})
    species = load_data("species.json")
    asset = species.get(asset_id) or {}
    bodies = [actor for actor in save.get("actors_data") or [] if not is_boat(actor) and actor.get("asset_id") == asset_id]  # every lineage of the kind

    # Counts drop at zero, the podium reads them all; the panel shows `evolved_from` alone, `evolution_id` read from its other end — the rest is the chronicler's.
    return {
        **{key: value for key, value in own.items() if value},
        "attack": asset.get("attack"),
        # The faiths, tongues, crowns and lineages its living hold between them, which no single lineage's `breakdown` says: `full` keeps the lineage's alone.
        **({"breakdown": {k: v for k, v in shares.items() if k != "species"}} if detailed and (shares := population_breakdown(bodies, ctx)) else {}),
        "description": asset.get("description"),
        "evolution_id": asset.get("evolution_id"),
        "evolved_from": min((beast for beast, spec in species.items() if spec.get("evolution_id") == asset_id), default=None),  # one beast a kind, in WB's lists
        "has_soul": asset.get("has_soul"),
        "id": asset_id,
        "pairing": _pairing(save, bodies, ctx),  # its next birth, a kind's own: a pair never minds the lineage
        **({"ranks": ranks} if ranks else {}),
    }


# WB `ActorAsset.name_taxonomic_*`, lower-case in the DLL. Its `species` rank is dropped: `metadata.name` already carries it, mutated (`Banditus Nikonisum`).
def _build_taxonomy(subspecies: dict) -> dict:
    ranks = (load_data("species.json").get(subspecies.get("species_id")) or {}).get("taxonomy") or {}
    return {rank: name.capitalize() for rank in _TAXONOMY_RANKS if (name := ranks.get(rank))}


# Two libraries: `biology` what WB mutated the subspecies into, `birth` what its newborns inherit — lists as `actor`'s, each id with its group under `full`.
def _build_traits(subspecies: dict, detailed: bool) -> dict:
    build = build_trait_list if detailed else partial(build_trait_ids, key="group")
    # WB reads a biology's faculties off its traits' tags (`Subspecies.cacheTags`) — each spelled-out entry carries its own, so they ride the named section alone.
    carried = {
        "biology": build(subspecies.get("saved_traits") or [], load_data("subspecies-traits.json")),
        "birth": build(subspecies.get("saved_actor_birth_traits") or [], load_data("creature-traits.json")),
    }
    return carried if detailed else light(carried)


# Whether a birth waits `maturation`: a pair's or a virgin's only if viviparous (an egg is laid at once), buds and sprouts always, a fission or a spore never.
def _carried(traits: frozenset[str]) -> bool:
    if traits & _UNCARRIED:
        return False
    return "reproduction_strategy_viviparity" in traits if traits & _STRATEGIC else True


# `--filter` of `--roster`: `sapient` or `beasts`, `type:<kind>`, and under `--since` a part, comma-separated.
def _filter_arg(value: str) -> list[str]:
    words = [word for word in value.split(",") if word]
    if stray := [word for word in words if word not in (*_MINDS, *_PARTS) and not word.startswith("type:")]:
        raise ArgumentTypeError(f"`{', '.join(stray)}`: `--roster` takes sapient, beasts, type:<kind> — and under `--since` {', '.join(_PARTS)}")
    return words


# The lineages a span saw rise and die out, one roll by id: `died` as the last save to hold them knew them, `arrived` as this one does, `came_and_went` no save held.
def _lineages_since(save: dict, since: str, chapter: str | None, kinds: set[str] | None, minded: bool | None, breeding: bool) -> list[dict]:
    earlier, saves = load_save(SAVES_DIR / since / "map.wbox"), since_saves(since, chapter, save)
    then = {row["id"]: row for row in _build_lineages(earlier, kinds, minded, breeding)}
    now = {row["id"]: row for row in _build_lineages(save, kinds, minded, breeding)}
    seen = {}
    for rows in (then.values(), *(_build_lineages(reading, kinds, minded, breeding) for reading in saves[:-1])):  # as its last save alive knew it
        seen |= {row["id"]: row for row in rows if row["members"]}  # WB keeps an emptied record a while: no living, no lineage
    died = [{**row, "part": "died"} for lid, row in seen.items() if not (now.get(lid) or {}).get("members")]
    arrived = [{**row, "part": "arrived"} for lid, row in now.items() if lid not in then and row["members"]]
    # The lineages no save held, by the kind the register gives their dead: their mind unknown, a roll by mind leaves them out
    came = (passed_unseen(earlier, saves).get("subspecies") or []) if minded is None else []
    kind_of = {dead["subspecies"]: dead["asset_id"] for dead in kept_deaths(save).values()} if came else {}
    unseen = [{"asset_id": kind_of.get(lid), "id": lid, "part": "came_and_went"} for lid in came if not kinds or kind_of.get(lid) in kinds]
    return sorted([*died, *arrived, *unseen], key=lambda row: row["id"])


# WB `canFallInLoveWith` between two of a kind: neither pledged to a third, no blood — parent, child or a parent shared — and opposite sexes where sexed.
def _may_mate(a: dict, b: dict, sexed: bool) -> bool:
    if a.get("lover") not in (None, b["id"]) or b.get("lover") not in (None, a["id"]):
        return False
    parents_a, parents_b = {a.get("parent_id_1"), a.get("parent_id_2")} - {None}, {b.get("parent_id_1"), b.get("parent_id_2")} - {None}
    if a["id"] in parents_b or b["id"] in parents_a or parents_a & parents_b:
        return False
    return not sexed or a.get("sex") != b.get("sex")


# The kind's first couple by WB's `canFallInLoveWith`, dated by the later breeding age (`now` once both hold); today's gap, walked on one shared land only.
def _pairing(save: dict, bodies: list[dict], ctx: dict) -> dict | None:
    if not bodies:
        return None
    island_of, walk_map = ctx["island_lookup"](), None  # the context `main` built: its trait libraries, its islands, loaded once
    grid, laws = LazyTileGrid(save), world_laws(save)
    # Traits and breeding are a lineage's, read once each: a kind's bodies share a handful of lineages, and every pair below asks of both.
    traits = {sub["id"]: frozenset(sub.get("saved_traits") or ()) for sub in save.get("subspecies") or []}
    mode, empty = {sid: breeding_mode(lineage) for sid, lineage in traits.items()}, frozenset()
    unfed = {sub["id"] for sub in save.get("subspecies") or [] if spores_unfed(sub)}  # spores no meal will ever let go: no date to give them
    carry = {sid: maturation_months(lineage, ctx) * UNITS_PER_MONTH if _carried(lineage) else 0 for sid, lineage in traits.items()}  # the bearer's sets it
    now = ctx["world_time"]  # a birth is today's at the earliest — and may be, WB saving no status: a `pregnant` begun before the save shows nowhere

    ready = {actor["id"]: crossed_at(actor, breeding_age(actor, ctx)) for actor in bodies}
    where = {actor["id"]: actor_xy(actor) for actor in bodies}
    mating = [actor for actor in bodies if mode.get(actor.get("subspecies")) == "mate"]
    row: dict = {}
    births = []
    lone = [actor for actor in bodies if mode.get(actor.get("subspecies")) == "alone"]
    if fed := [actor for actor in lone if actor.get("subspecies") not in unfed]:  # a lineage breeding alone needs no partner
        row["alone_on"] = min(ready[actor["id"]] for actor in fed)
        if any(_SOULBORNE in traits.get(actor.get("subspecies"), empty) for actor in fed):  # WB births it once a blow has struck a soul
            row["needs"] = "soul"
        births += [max(ready[actor["id"]] + carry.get(actor.get("subspecies"), 0), now) for actor in fed]
    sexed = {actor["id"]: _SEXED in traits.get(actor.get("subspecies"), empty) for actor in mating}
    bars = {actor["id"]: _breeding_bars(actor, ctx, island_of, grid, save["tileMap"]) for actor in mating}
    # WB's law on babies, a beast's or a thinker's, read off the kind's first lineage that mates — every one of a kind thinks or none does.
    law = "world_law_civ_babies" if mating and is_sapient(ctx["subspecies_by_id"].get(mating[0].get("subspecies"))) else "world_law_animals_babies"
    barred_by_law = {law} if not laws.get(law, True) else set()
    # Lovers first, WB never parting them; then a pair nothing bars — a law always, a body's state only if ready now; then the earliest, the nearest.
    best = min(
        (
            (
                a.get("lover") != b["id"],
                bool(barred := sorted((bars[a["id"]] | bars[b["id"]] if (mates := max(ready[a["id"]], ready[b["id"]])) <= now else set()) | barred_by_law)),
                mates,
                walk_tiles(where[b["id"]][0] - where[a["id"]][0], where[b["id"]][1] - where[a["id"]][1]),
                a,
                b,
                barred,
            )
            for i, a in enumerate(mating)
            for b in mating[i + 1 :]
            if _may_mate(a, b, sexed[a["id"]] or sexed[b["id"]])
        ),
        key=lambda pair: pair[:4],
        default=None,
    )
    if best:
        apart, _, row["mates_on"], crow, a, b, barred = best
        sexual = sexed[a["id"]] or sexed[b["id"]]
        bearer, other = (b, a) if sexual and b.get("sex") == 1 else (a, b)  # a sexed pair's mother carries (WB `checkForBabies`)
        row |= {
            "barred": _bars_told(barred) or None,
            "crow_tiles": round(crow),
            "drawn": True if not sexual else None,  # no mother to put first: the bearer is drawn at the birth itself
            "lovers": True if not apart else None,
            "pair": [bearer["id"], other["id"]],  # the bearer first, whose town the child joins (WB `BabyMaker.makeBaby`), else the other's
        }
        # Lovers may carry already, unseen, where the save keeps no status; where it does, they wait out the afterglow of their last kiss.
        glow = max(status_left(a, "afterglow") or 0, status_left(b, "afterglow") or 0)
        conceived = max(row["mates_on"], now + glow) if apart or status_left(bearer, "pregnant") is not None else row["mates_on"]
        births.append(max(conceived + carry.get(bearer.get("subspecies"), 0), now))
        (ax, ay), (bx, by) = where[a["id"]], where[b["id"]]
        if (land := island_of.get((ax, ay))) is not None and land == island_of.get((bx, by)):
            walk_map = walk_map or WalkMap(save)
            if (way := walk_way(walk_map, walk_map.gait(None, frozenset()), ax, ay, {by * walk_map.width + bx})) is not None:
                row["walk_tiles"] = round(way[3])  # the tiles trodden between them, not the way's cost
                if row["walk_tiles"] == row["crow_tiles"]:  # a straight way says its length once
                    del row["crow_tiles"]
    elif not mating and not lone:  # no lineage of the kind holds a breeding trait: it never breeds
        row["missing"] = "reproduction"
    elif mating:  # a partner wanted, none to be had: a sexed kind of one sex says which, else blood or pledges bar every pair
        sexes = {sex_label(actor) for actor in mating}
        row["missing"] = ({"female": "male", "male": "female"}[sexes.pop()]) if len(sexes) == 1 and all(sexed.values()) else "partner"
    elif not fed:  # breeding alone, but by spores a body with no stomach never sheds
        row["missing"] = "meal"
    # A barren lineage beside fertile ones, its bodies by lineage: WB wants `needs_mate` of both lovers, so none of them ever pairs, not even across lineages.
    if (mating or lone) and (barren := Counter(sid for actor in bodies if (sid := actor.get("subspecies")) is not None and mode.get(sid) is None)):
        row["barren"] = {str(sid): count for sid, count in sorted(barren.items())}  # ids as JSON keys, in their numeric order
    if births:  # the pair's own, never a bearer's outside it: a line reads as one couple's
        row["birth_on"] = min(births)
    # A birth under way, as the save keeps it: its date is the game's own, apart as `due` — its bearers counted, each by `actor --roster`.
    if carrying := [left for actor in bodies if (left := max(status_left(actor, status) or 0 for status in _CARRYING))]:
        row["pregnant"], row["due"] = len(carrying), now + min(carrying)

    for key in ("alone_on", "birth_on", "due", "mates_on"):  # the hours dated: `now` for what already holds
        if key in row:
            row[key] = "now" if row[key] <= now else world_date(row[key])
    return row


# What a biology is ranked on among the world's others. Living counts come off the rosters that one actor pass built — the podium weighs every biology.
def _rank_getters(members: dict, housed: Counter, money: Counter, renown: Counter, warriors: Counter, world_time: float) -> dict:
    return {
        "age": lambda s: entity_age(s, world_time),
        "births": lambda s: int(s.get("total_births") or 0),
        "births_per_death": lambda s: int(s.get("total_births") or 0) / d if (d := int(s.get("total_deaths") or 0)) else 0.0,
        # The reach `metadata` already prints, ranked as a custom and a creed rank theirs — both read off the one actor pass, no second walk.
        "cities": lambda s: len({cid for a in members.get(s["id"], ()) if (cid := a.get("cityID"))}),
        "deaths": lambda s: int(s.get("total_deaths") or 0),
        "housed_pct": lambda s: housed[s["id"]] / n if (n := len(members.get(s["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kills": lambda s: int(s.get("total_kills") or 0),
        # Per-head, so a small body can out-rank a wide one — floored at `MIN_PER_CAPITA_UNITS`, under which the divisor speaks louder than the body.
        "kills_per_capita": lambda s: int(s.get("total_kills") or 0) / n if (n := len(members.get(s["id"], ()))) >= MIN_PER_CAPITA_UNITS else 0.0,
        "kingdoms": lambda s: len({kid for a in members.get(s["id"], ()) if (kid := a.get("civ_kingdom_id"))}),
        "members": lambda s: len(members.get(s["id"], ())),
        "money": lambda s: money[s["id"]],
        "renown_total": lambda s: renown[s["id"]],  # WB's own `renown` only counts births; this one is the renown its bearers carry
        "warriors": lambda s: warriors[s["id"]],
    }


# `--roster`: every living lineage by its id, as `subspecies … metadata` tells it, `--filter` narrowing, `--since` the risen and the died out instead.
def _roster(argv: list[str]) -> int:
    try:
        since, argv = take_since(argv)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    save_path, argv, chapter = take_chapter(argv)
    parser = arg_parser(prog="subspecies/info.py --roster", taken="[--since C<n>] [C<n>]", gloss="subspecies.roster")
    parser.add_argument("--filter", action="append", type=_filter_arg, metavar="sapient|beasts|type:<kind>,…")
    parser.add_argument("--limit", type=limit_arg, metavar="n|all")
    parser.add_argument("--with", action="append", dest="fields", metavar="reproduction")
    args = parser.parse_args(argv)
    words = {word for taken in args.filter or () for word in taken}
    if {"beasts", "sapient"} <= words:
        print("✗ beasts and sapient split the lineages in two: filter by one", file=sys.stderr)
        return 2
    kinds = ",".join(sorted(word.removeprefix("type:") for word in words if word.startswith("type:"))) or None  # kinds add up, as `asset_kinds` reads them
    minded = True if "sapient" in words else False if "beasts" in words else None
    parts = [word for word in _PARTS if word in words] or list(_PARTS)
    if parts != list(_PARTS) and not since:  # a part is what befell a lineage since a chapter
        print(f"✗ {', '.join(parts)}: parts of `--since C<n>` — name a chapter", file=sys.stderr)
        return 2
    if since and not (SAVES_DIR / since / "map.wbox").exists():
        print(f"✗ no save for {since}", file=sys.stderr)
        return 2
    limit = LIMIT if args.limit is None else args.limit or None  # `all` read as 0: every line
    if stray := [field for field in args.fields or () for field in field.split(",") if field and field != "reproduction"]:
        print(refused("--with", stray, ["reproduction"], "`gloss subspecies.roster.--with`, `subspecies <id>`"), file=sys.stderr)
        return 2
    breeding = bool(args.fields)
    save = load_save(save_path)
    families = asset_families(save) if kinds else {}
    bred = asset_kinds(families, kinds) if kinds else None
    of = f" of {kinds}" if kinds else ""
    rows = (
        [row for row in _lineages_since(save, since, chapter, bred, minded, breeding) if row["part"] in parts]
        if since
        else _build_lineages(save, bred, minded, breeding)
    )
    if not rows:  # a mistyped word told apart from a kind with no lineage left
        quiet = f"no lineage{of} came or went since {since}" if since else (kinds and unsited_reason(families, kinds)) or f"no living lineage{of} in this world"
        print(f"✗ {quiet}", file=sys.stderr)
        return 1
    # What a filter fixes goes unsaid: a mind asked, `sapient`; one kind asked, `asset_id` — and a field `--with` adds drives `born` off, the line kept inline
    unsaid = {*(["sapient"] if minded is not None else []), *(["asset_id"] if one_kind(bred) else [])}
    lines = []
    for row in rows:  # `reproduction`, the one field `--with` puts on, drives one off as on every roll
        own = {key: value for key, value in row.items() if key not in unsaid and key != "reproduction"}
        lines.append((row["id"], row["id"], make_room(own, {key: row[key] for key in ("reproduction",) if key in row}, _GIVES_WAY)))
    emit(roll(told_part(lines, parts) if since else lines, limit, "lineages", "by id"))
    return 0


# Every species alive, each with the standing the panel ranks it on: one pass over the actors, so a subspecies costs the same whichever stock it sprang from.
def _species_totals(save: dict) -> dict[str, dict]:
    # Factories rather than `setdefault`, which would mint a row and two sets per actor merely to keep the first — thousands of them over a mature world.
    cities: defaultdict[str, set] = defaultdict(set)
    kingdoms: defaultdict[str, set] = defaultdict(set)
    totals: defaultdict[str, dict] = defaultdict(_EMPTY_SPECIES.copy)
    for actor in save.get("actors_data") or []:
        if is_boat(actor) or not (asset_id := actor.get("asset_id")):
            continue
        entry = totals[asset_id]
        entry["pop"] += 1
        entry["renown"] += int(actor.get("renown") or 0)
        if city := actor.get("cityID"):
            cities[asset_id].add(city)
        if kingdom := actor.get("civ_kingdom_id"):
            kingdoms[asset_id].add(kingdom)
    for entry_id, entry in totals.items():
        entry["cities"] = len(cities.get(entry_id, ()))
        entry["kingdoms"] = len(kingdoms.get(entry_id, ()))
    for sub in save.get("subspecies") or []:  # how many biologies WB has mutated out of the stock, the one count that is the species' alone
        if (sid := sub.get("species_id")) in totals:
            totals[sid]["subspecies"] += 1
    return totals


def main(argv: list[str]) -> int:
    if "--roster" in argv:  # every living lineage: its own options, no id
        return 2 if (rest := roster_call(argv, "lineage", "subspecies")) is None else _roster(rest)
    save_path, argv, chapter = take_chapter(argv)
    if not argv or argv[0] in ("-h", "--help"):
        return hand_usage("usage: subspecies/info.py <id> [sections] [C<n>] | --roster [options]\neach option: `gloss subspecies`", argv)
    try:
        subspecies_id = int(argv[0])
    except ValueError:
        print(f"✗ invalid id: {argv[0]}", file=sys.stderr)  # a malformed call, like a bad section — not an entity that happens to be missing
        return 2

    requested = sections_arg(argv)
    try:
        sections = parse_sections(requested, _ALL_SECTIONS)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    save = load_save(save_path)
    subspecies_by_id = index_by_id(save.get("subspecies") or [])
    subspecies = subspecies_by_id.get(subspecies_id)
    if subspecies is None:
        print(absent_entity("subspecies", "subspecies", subspecies_id, chapter), file=sys.stderr)
        return 1

    # One pass groups the living by the biology they carry: WB points the actor at its subspecies, never the reverse. Skipped whole where no section asked.
    housed, money, renown, warriors = Counter(), Counter(), Counter(), Counter()
    members_by_id: defaultdict[int, list] = defaultdict(list)  # a factory, `setdefault` costing a fresh list per actor to throw it away on all but the first
    for actor in (save.get("actors_data") or []) if not _NEEDS_ACTORS.isdisjoint(sections) else ():
        if sid := actor.get("subspecies"):
            members_by_id[sid].append(actor)

    # The four sums answer to the podium alone, so they are read off the rosters once those stand — a section that wants none of them pays for none of them.
    if "ranks" in sections:
        for sid, group in members_by_id.items():
            roofs = coins = fame = fighters = 0
            for actor in group:
                roofs += bool(actor.get("homeBuildingID"))
                coins += int(actor.get("money") or 0)
                fame += int(actor.get("renown") or 0)
                fighters += actor.get("profession") == PROFESSION_WARRIOR
            housed[sid], money[sid], renown[sid], warriors[sid] = roofs, coins, fame, fighters

    members = members_by_id.get(subspecies_id, [])
    ctx = {
        **build_actor_stats_context(save),  # brings the trait libraries and `languages_by_id`, `world_time` with them
        "actors_by_id": index_by_id(save.get("actors_data") or []),  # `pop_of` pairs lovers through it, and only a mutual pair counts
        "cultures_by_id": index_by_id(save.get("cultures") or []),
        "families_by_id": index_by_id(save.get("families") or []),
        "island_lookup": cache(lambda: compute_islands_cached(save, save_path)[1]),  # tile → island id, called not stored: `metadata` alone reads it
        "kingdoms_by_id": index_by_id(save.get("kingdoms") or []),  # `population_breakdown` alone reads it here — a biology answers to no crown of its own
        "religions_by_id": index_by_id(save.get("religions") or []),
        "subspecies_by_id": subspecies_by_id,  # the index the id was checked against, so the context's own copy never takes over
    }

    out, detailed = {}, requested not in (None, "full")  # a section named, not `full`'s summary
    if "breakdown" in sections:
        # The living against the biology they were born into. Species and subspecies both go: WB fixes them at birth, so each would read 100 % and say nothing.
        out["breakdown"] = {k: v for k, v in population_breakdown(members, ctx).items() if k not in ("species", "subspecies")}
    if "leaders" in sections:  # WB names no such podium — ours, and it drops below four members, where a champion among three names nobody
        out["leaders"] = settlement_leaders(members, ctx, children_by_id(save), lambda a: compute_actor_stats(a, ctx))
    if "metadata" in sections:
        out["metadata"] = _build_metadata(subspecies, members, ctx)
    if "pop" in sections:
        out["pop"] = _build_pop(members, ctx)
    if "ranks" in sections:
        getters = _rank_getters(members_by_id, housed, money, renown, warriors, ctx["world_time"])
        out["ranks"] = competition_ranks(subspecies, list(subspecies_by_id.values()), getters)
    if "species" in sections:
        species = _build_species(subspecies, save, ctx, detailed=detailed)
        out["species"] = species if detailed else light(species, withheld="breakdown")
    if "stats" in sections:
        out["stats"] = subspecies_stats(subspecies, ctx)
    if "taxonomy" in sections:
        out["taxonomy"] = _build_taxonomy(subspecies)
    if "traits" in sections:
        out["traits"] = _build_traits(subspecies, detailed=detailed)

    emit(out)
    return 0


if __name__ == "__main__":
    sys.exit(run(main))

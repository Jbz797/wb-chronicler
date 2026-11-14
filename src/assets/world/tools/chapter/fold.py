# What a chapter keeps of each tool's output: `new.py` hands its blocks here before writing `chapter.json`, cut to what the reader's panels print.
# Nothing is lost to the chronicler — every section cut here is one `<tier>/info.py` still hands over whole.

# What no panel reads, cut by its section and never by name alone — `nobles` and `loot` have homonyms. A tier shedding more says so in `_AUDIT_TIERS`.
_AUDIT = {
    "army": frozenset({"captain_years", "id", "men", "total_captains", "women"}),  # its id, tenure, captains and sexes — the panel names the one in post
    "companions": frozenset({"lover_since"}),  # the couple's date: the panel names the mate, never since when
    "identity": frozenset({"founding_city", "founding_clan", "founding_kingdom", "motto", "name_culture", "name_template_set", "worldview"}),
    "metadata": frozenset(
        {
            "adult_on",
            "age_since",
            "age_stage",
            "alliance",  # the pact a realm or a soul answers to — the panel has a tier of its own for it, and the scripts still hand the ref over
            "army_since",
            "beside_building",
            "besieged_by",
            "born",  # when WB set it on the map, a soul or a people — for the chronicler's « who came first », no panel dating either
            "breeding_barred",
            "breeds_on",
            "can_reproduce",
            "city_since",
            "clan_chief_years",
            "date",  # the world's day as the chronicler reads it — the panels take the clock through `index.json`
            "deaths_by_cause",
            "families",
            "favorite_food",
            "founding_city",
            "founding_kingdom",
            "gen",
            "hatch_on",
            "hatches_as",
            "home",
            "in_building",
            "island_id",
            "islands",
            "islet",
            "mass",
            "motto",
            "near_places",
            "peace_time",
            "place",
            "settle",  # the chronicler's « why no town yet »: no panel says who could found one
            "settle_more",
            "status_history",
            "statuses",
            "statuses_left",
            "task",
            "task_history",
            "task_target",
            "tax_local",
            "tax_tribute",
            "traits",
            "under_construction",  # a town's and a crown's sites, counted among the `buildings` the panel prints
            "zone_of",
        }
    ),
    "ranks": frozenset(
        {
            "army_captain_years",
            "army_kills_per_death",
            "birth_rate",
            "births",
            "births_per_death",
            "damage_min",
            "gold",
            "kills_per_capita",
            "kills_per_death",
            "loot",
            "nobles",
            "nobles_money",
            "pop_per_city",
            "renown_per_capita",
            "ruler_money",
            "subjects_money",
            "traits",
        }
    ),
    # The tie's age, its border or its gap, its last war: the panel prints the standing, its drivers.
    "relations": frozenset({"age_years", "borders", "gap_tiles", "years_since_last_war"}),
    # The world's stock of items, its sky, what its bodies are in the middle of and its sites — the panel counts souls, roofs and trees.
    "snapshot": frozenset({"clouds", "gear", "statuses", "under_construction"}),
    "stats": frozenset({"accuracy", "birth_rate", "births", "bonus_towers", "damage_min", "loot", "opinion", "projectiles", "recoil", "swim", "throwing_range"}),
}

# What a tier sheds on top of its bare section, united with it where the cut is read — the bare one stays the only truth a change has to touch.
_AUDIT_TIERS = {
    # A people's health is charted by a town and a crown alone: no other body's panel prints it, and `<tier>/info.py <id> pop` still counts it
    **{f"{tier}.pop": {"immortals", "infected", "sick"} for tier in ("alliance", "clan", "culture", "family", "language", "religion", "subspecies")},
    "alliance.kingdoms": {"pop"},  # each member a tag, its headcount the crown's own panel to print
    "alliance.metadata": {"cities", "kingdoms"},  # the pact names its realms and towns as tags, so counting either says nothing the list has not
    "alliance.ranks": {"cities", "kingdoms", "money", "renown_total"},  # among two pacts a podium says less still; `age` and `warriors` are printed
    "attackers.kingdoms": {"pop"},  # a camp's realms as tags, the side's pooled `pop` printed beside them
    "city.identity": {"clan", "culture", "language", "religion", "subspecies"},  # the bodies the town answers to — the panel names its founder alone
    # No row counts its births, its crown and seat are the kingdom panel's to name, and its migrants, centre and month under the banner only the chronicler reads.
    "city.metadata": {"at", "births", "capital", "kingdom", "kingdom_since", "migrants"},
    "city.pop": {"money"},  # « Richesse » prints the shares and `metadata.wealth`, never the purse they split
    "city.ranks": {"money"},  # the purse the shares split, which « Richesse » prints bare, ranked for the chronicler alone
    "clan.identity": {"culture", "species", "subspecies"},  # its custom and the founder's stock — the panel names the founder alone, as a culture's does
    "clan.metadata": {"births"},  # unlike a family, a pact or a biology, the clan panel prints no births row
    "culture.identity": {"species", "subspecies"},  # the founder's stock — the panel names the founder alone, whose own tag carries it
    "defenders.kingdoms": {"pop"},  # as `attackers`
    "family.identity": {"culture", "species", "subspecies"},  # the family is read by the souls it seated, its blood and its tongue answering from their own tiers
    "family.metadata": {"kingdoms", "parents"},  # a second crown or a parent line is too rare for a panel row, so both ride the script's output alone
    "family.ranks": {"cities", "kingdoms"},  # towns and crowns follow the heads that hold them, so the podium repeats the one `members` already draws
    # The bodies it belongs to, each read to open its own tier block, its stock, which the portrait draws off the persons registry, and years `age` holds
    "favorite.metadata": {"age_overgrowth", "asset_id", "city", "clan", "culture", "family", "kingdom", "language", "religion", "subspecies"},
    "kingdom.identity": {"clan", "culture", "language", "religion", "subspecies"},  # as a town's
    "kingdom.metadata": {"births", "ferries", "max_cities"},  # as a town's; whether a crown ferries, what it can hold: rules of the chronicle, not rows
    "kingdom.pop": {"money"},  # as a town's
    "kingdom.ranks": {"money"},  # as a town's
    "language.identity": {"species", "subspecies"},  # the founder's stock, as a culture's
    "language.metadata": {"lost"},  # speakers gone to another tongue: the panel prints those born to it and won to it, the chronicler the loss
    "language.ranks": {"lost"},  # as its metadata
    "religion.identity": {"species", "subspecies"},  # the founder's stock, as a culture's
    "subspecies.species": {"attack", "description", "evolution_id", "has_soul", "pairing"},  # the parent stock's own, all the chronicler's: the panel prints none
    "wars.metadata": {"deaths", "started_by"},  # the card sets each camp's toll and crown, never the sum or the man — `war/info.py <id>` hands over both
}

# No panel reads them: `report` and `info` are per-call, `taxonomy` comes from `identity.species`, `passengers` and `kin` are the chronicler's own reading.
_CHRONICLER_ONLY = frozenset({"age_description", "age_name", "info", "kin", "passengers", "report", "sapient", "taxonomy"})

# `pop` keys no panel reads — the chronicler still gets them whole from `<tier>/info.py <id> pop`, they simply don't ride along in the chapter.
_DEMOGRAPHY = frozenset(
    {"adults", "babies", "children", "couples", "eaters", "eggs", "elders", "familyless", "gen_deepest", "gen_median", "happy", "men", "nobles", "teens", "women"}
)

# A tier the favorite holds none of, a war-free crown: said by the key absent. Never `{"total": 0}` — `emit` drops an empty shelf, and an opinion at 0 is a reading.
_EMPTY = (None, [], {})

# The podium rows a panel names, mirroring `LEADER_CLAN_ROWS`/`LEADER_PERSON_ROWS` (`stats.constant.ts`). The rest stays in `<tier>/info.py <id> leaders`.
_LEADER_ROWS = {"clans": frozenset({"pop"}), "persons": frozenset({"kills", "level", "money", "oldest", "renown"})}

_OTHER_DEATHS = ("ash_fever", "none", "other")  # the ash fever, the deaths WB files under no cause or its catch-all (heat, sun, a fish ashore…): one « other » row

# Libraries and fleets kept as a count alone — the tier's own `info.py <id> <section>` still names every volume and hull behind the figure.
_TALLIES = {
    "culture": ("books",),
    "kingdom": ("boats",),
    "language": ("books",),
    "religion": ("books",),
}

# The counters « Activité récente » prints, mirroring `CUMULATIVE_STATS` (`stats.constant.ts`), `deaths` riding along for the breakdown panel below it.
_UI_CUMULATIVE = frozenset({"books_burnt", "books_read", "cities_conquered", "cities_rebelled", "deaths", "evolutions", "metamorphosis", "plots_succeeded"})
_UI_UNSHOWN_RECORDS = {"persons": frozenset({"equipment_power"})}  # the one record the « Palmarès » (`LEADER_GROUPS`, `stats.constant.ts`) has no row for
_UI_UNSHOWN_ZERO = frozenset({"critical_chance"})  # a floor the chronicler reads as a fact (`_KEEP_ZERO`), where the panel has nothing to show


# The one name a panel prints per record: a shared first place travels as its first holder, bare of the count the chronicler reads off the script.
def _first_holder(holders: list[dict]) -> dict:
    return {k: v for k, v in holders[0].items() if k != "value"}


# The wars a pact's members are drawn into — the chapter fields the crowns' own under `wars`, and `alliance/info.py <id> wars` still names the pact's.
def _fold_alliance_detail(alliance: dict) -> None:
    alliance.pop("wars", None)


# The panel prints the hull's name, stock, crown, port, age and health; `boat/info.py <id>` has the rest. `kind` goes: WB boards souls onto `$boat_transport$` alone.
def _fold_boat_detail(boat: dict) -> None:
    (boat.get("identity") or {}).pop("kind", None)
    for section in ("combat", "traits"):
        boat.pop(section, None)  # a hull's merits — `kingslayer`, `veteran` — narrate well and print nowhere
    metadata = boat.get("metadata") or {}
    for key in ("at", "kills", "level", "loot", "mass_kg", "renown", "speed"):  # a hull is no pin on the map, where the favourite is; `home` goes with `_AUDIT`
        metadata.pop(key, None)


# The composition table names each dimension's leader and its share: the runners-up print nowhere, and a leader holding everyone restates its own panel.
def _fold_breakdown(entity: dict) -> None:
    block = entity.pop("breakdown", None) or {}
    if kept := {dimension: rows[:1] for dimension, rows in block.items() if isinstance(rows, list) and rows[0]["pct"] < 100}:  # `info`, a lone line, no row
        entity["breakdown"] = kept


# Drops the loyalty summary and both stock lists, keeping their `total`, and the mayors past — the panels print those alone, the sections still itemising the rest.
def _fold_city_detail(city: dict) -> None:
    (city.get("loyalty") or {}).pop("top_drivers", None)
    _fold_rulers(city)
    _fold_total(city, "books", "gear")


# Cut to what « Activité récente » charts — WB tallies a good deal more, and `world/info.py <chapter> cumulative` still hands the chronicler every one of them.
def _fold_cumulative(world: dict) -> None:
    if isinstance(block := world.get("cumulative"), dict):
        world["cumulative"] = {key: value for key, value in block.items() if key in _UI_CUMULATIVE}
        deaths = world["cumulative"].get("deaths") or {}
        if others := sum(deaths.pop(cause, 0) for cause in _OTHER_DEATHS):  # one row of the panel for the three WB files apart from its own causes
            deaths["other"] = others


# Drops every `opinion.top_drivers`, the kings past and the town list: the table prints the standing, the panel the sitting king, the founder and a town count.
def _fold_kingdom_detail(kingdom: dict) -> None:
    kingdom.pop("cities", None)
    for relation in kingdom.get("relations") or []:
        (relation.get("opinion") or {}).pop("top_drivers", None)
    if founder := _fold_rulers(kingdom):
        kingdom.setdefault("identity", {})["founder"] = founder
    _fold_total(kingdom, "gear")


# A tier's podium cut to the six rows its panel names, each to its first holder — the ones it never prints outweighing the ones it does.
def _fold_leaders(entity: dict) -> None:
    if not isinstance(podium := entity.get("leaders"), dict):
        return
    entity["leaders"] = {}  # `unranked` and the families go with the unprinted rows: the chronicler's, no panel's — and a block naming nobody
    for block, kept in _LEADER_ROWS.items():
        if isinstance(rows := podium.get(block), dict) and (named := {key: _first_holder(refs) for key, refs in rows.items() if key in kept}):
            entity["leaders"][block] = named


# The age and sex slices, the lineage depth, the count of nobles — figures the chronicler writes with and no panel prints. `pop` keeps what the UI reads.
def _fold_pop(entity: dict) -> None:
    if isinstance(block := entity.get("pop"), dict):
        entity["pop"] = {k: v for k, v in block.items() if k not in _DEMOGRAPHY}


# The sitting ruler alone and undated, the panels naming no other. Returns the first reign's `{id, name}`, a crown's founder — a town's is its first settler.
def _fold_rulers(entity: dict) -> dict | None:
    block = entity.pop("rulers", None) or []
    if not (line := [block["first"], *block["latest"]] if isinstance(block, dict) else block):
        return None
    if "to" not in line[-1]:
        entity["rulers"] = [{key: line[-1][key] for key in ("id", "name") if key in line[-1]}]
    return {key: line[0][key] for key in ("id", "name") if key in line[0]}


# `stats` goes here rather than through `_CHRONICLER_ONLY`, which would take the favorite's own block along with it.
def _fold_subspecies_detail(subspecies: dict) -> None:
    subspecies.pop("stats", None)


# The panels read nothing but the `total`, whichever form `full` handed over — nothing is lost, the chapter's own `map.wbox` replaying any section.
def _fold_total(entity: dict, *keys: str) -> None:
    for key in keys:
        if isinstance(block := entity.get(key), dict):
            entity[key] = {"total": block.get("total", 0)}


# Every record the world's « Palmarès » prints, each to its first holder — `world/info.py <chapter> leaders` naming them all, the unprinted ones too.
def _fold_world_leaders(world: dict) -> None:
    if isinstance(block := world.get("leaders"), dict):
        block.pop("unranked", None)  # why a group stayed empty: the chronicler's, no panel's
        world["leaders"] = {
            group: {row: _first_holder(holders) for row, holders in rows.items() if row not in _UI_UNSHOWN_RECORDS.get(group, ())} for group, rows in block.items()
        }


def _without(block: dict, cut: frozenset) -> dict:
    return {key: value for key, value in block.items() if key not in cut}


# Whole years from one `y<year> m<month>` to another, counted by the month as the dates read.
def _years_between(since: str, now: str) -> int:
    (y1, m1), (y2, m2) = ((int(part[1:]) for part in date.split()) for date in (since, now))
    return (y2 * 12 + m2 - y1 * 12 - m1) // 12


# `_CHRONICLER_ONLY` cuts at every depth, `_AUDIT` from one named section; the empties a cut leaves go too, and the one nought kept for the chronicler alone.
def drop_chronicler_keys(node: object, parent: str = "") -> object:
    if isinstance(node, dict):
        kept = {}
        for key, raw in node.items():
            if key in _CHRONICLER_ONLY:
                continue
            value = raw
            if cut := _AUDIT.get(key, frozenset()) | _AUDIT_TIERS.get(f"{parent}.{key}", frozenset()):  # a section is a dict, save `relations`, a list of them
                if isinstance(value, dict):
                    value = _without(value, cut)
                elif isinstance(value, list):
                    value = [_without(item, cut) if isinstance(item, dict) else item for item in value]
            if key == "stats" and isinstance(value, dict):
                value = {stat: n for stat, n in value.items() if n or stat not in _UI_UNSHOWN_ZERO}
            if (value := drop_chronicler_keys(value, key)) not in _EMPTY:  # absent, not empty: `render` keeps what `emit` strips, and the panels read it absent
                kept[key] = value
        return kept
    return [value for item in node if (value := drop_chronicler_keys(item, parent)) not in _EMPTY] if isinstance(node, list) else node


# What every tier sheds alike, then what its own panel spares — and the hull's crew, counted rather than listed.
def fold_bodies(blocks: dict, boat: dict | None) -> None:
    folds = {
        "alliance": _fold_alliance_detail,
        "city": _fold_city_detail,
        "kingdom": _fold_kingdom_detail,
        "subspecies": _fold_subspecies_detail,
    }
    for tier, block in blocks.items():
        if not block:
            continue
        _fold_breakdown(block)
        _fold_leaders(block)
        _fold_pop(block)
        block.pop("traits", None)  # the raw list goes; `new.py` carries or asks for the chronicler's prose in its place
        if fold := folds.get(tier):
            fold(block)
        if keys := _TALLIES.get(tier):
            _fold_total(block, *keys)
    if boat:
        _fold_boat_detail(boat)
        _fold_total(boat, "crew")  # the panel prints how many souls are aboard, `boat/info.py <id> crew` names them


# Folds the favorite's heavy blocks: traits, gear and its own work, who stands around, victims and the scheme's detail go — `actor/info.py <id>` hands each whole.
def fold_favorite_detail(favorite: dict, now: str) -> None:
    for section, stat in (("crafted", "crafted"), ("victims", "kills")):  # the panel ranks its work and its kills among `stats`, where `actor` tells neither
        if total := (favorite.pop(section, None) or {}).get("total"):
            favorite.setdefault("stats", {})[stat] = total
    for section in ("gear", "surroundings"):
        favorite.pop(section, None)
    # The panel prints the type, the target and the gauge: WB's English is the chronicler's, and so is how long the scheme has run.
    plot = favorite.get("plot") or {}
    plot.pop("months", None)
    if kind := plot.get("type"):
        plot["type"] = {"id": kind.get("id")}
    favorite.pop("traits", None)  # the chronicler's summary takes its place, carried over or owed
    metadata = favorite.get("metadata") or {}
    if since := metadata.pop("tenure_since", None):  # the panel prints the post's whole years, the chronicler the month it began
        metadata["tenure_years"] = _years_between(since, now)


# The world block as its panels print it: the tallies and podiums folded, each scheme's type cut to its key.
def fold_world(world: dict) -> None:
    _fold_cumulative(world)
    _fold_world_leaders(world)
    _fold_total(world, "boats")  # counted, never listed: both panels print the count alone, `<tier>/info.py … boats` naming the hulls on demand
    for scheme in world.get("plots") or []:  # the schemer and the type's key: WB's English is the chronicler's, and the panel owns the French
        scheme["type"] = {"id": (scheme.get("type") or {}).get("id")}

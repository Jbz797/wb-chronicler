# What a chapter keeps of each tool's output: `new.py` hands its blocks here before writing `chapter.json`, cut to what the reader's panels print.
# Nothing is lost to the chronicler — every section cut here is one `<tier>/info.py` still hands over whole.

# What no panel reads, cut by its section and never by name alone — `nobles` and `loot` have homonyms. A tier shedding more says so in `_AUDIT_TIERS`.
_AUDIT = {
    "army": frozenset({"captain_years", "total_captains"}),  # the corps' tenure and its roll of captains — the panel names the one in post, and only him
    "identity": frozenset({"founding_city", "founding_clan", "founding_kingdom", "motto", "name_culture", "name_template_set", "worldview"}),
    "metadata": frozenset(
        {
            "adult_age",
            "alliance",  # the pact a realm or a soul answers to — the panel has a tier of its own for it, and the scripts still hand the ref over
            "besieged_by",
            "breeding_age",
            "can_reproduce",
            "clan_chief_years",
            "deaths_by_cause",
            "families",
            "favorite_food",
            "founding_city",
            "founding_kingdom",
            "gen",
            "hatch_months",
            "home",
            "in_building",
            "island_id",
            "islands",
            "mass",
            "months_until_next_age",
            "motto",
            "peace_time",
            "tax_local",
            "tax_tribute",
            "traits",
            "x",
            "y",
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
            "population_per_city",
            "renown_per_capita",
            "ruler_money",
            "subjects_money",
            "traits",
        }
    ),
    "ranks_in_species": frozenset({"birth_rate", "births", "damage_min", "loot"}),
    "relations": frozenset({"age_years", "borders"}),  # how long the tie has held and whether the two touch — the panel prints the standing and its drivers
    "snapshot": frozenset({"gear"}),  # the world's stock of items — the panel counts souls, roofs and trees, never a blade
    "stats": frozenset({"birth_rate", "births", "bonus_towers", "damage_min", "loot", "max_cities"}),
}

# What a tier sheds on top of its bare section, united with it where the cut is read — the bare one stays the only truth a change has to touch.
_AUDIT_TIERS = {
    # A people's health is charted by a town and a crown alone: no other body's panel prints it, and `<tier>/info.py <id> population` still counts it
    **{f"{tier}.population": {"immortals", "infected", "sick"} for tier in ("alliance", "clan", "culture", "family", "language", "religion", "subspecies")},
    "alliance.kingdoms": {"population"},  # each member a tag, its headcount the crown's own panel to print
    "alliance.metadata": {"cities", "kingdoms"},  # the pact names its realms and towns as tags, so counting either says nothing the list has not
    "alliance.ranks": {"cities", "kingdoms", "money", "renown_total"},  # among two pacts a podium says less still; `age` and `warriors` are printed
    "attackers.kingdoms": {"population"},  # a camp's realms as tags, the side's pooled `population` printed beside them
    "city.identity": {"clan", "culture", "language", "religion", "subspecies"},  # the bodies the town answers to — the panel names its founder alone
    "city.metadata": {"births", "capital", "kingdom"},  # no row counts its births, and its crown and seat are the kingdom panel's to name
    "city.population": {"money"},  # « Richesse » prints the shares and `metadata.wealth`, never the purse they split
    "city.ranks": {"money"},  # the purse the shares split, which « Richesse » prints bare, ranked for the chronicler alone
    "clan.identity": {"culture", "species", "subspecies"},  # its custom and the founder's stock — the panel names the founder alone, as a culture's does
    "clan.metadata": {"births"},  # unlike a family, a pact or a biology, the clan panel prints no births row
    "culture.identity": {"species", "subspecies"},  # the founder's stock — the panel names the founder alone, whose own tag carries it
    "defenders.kingdoms": {"population"},  # as `attackers`
    "family.identity": {"culture", "species", "subspecies"},  # the family is read by the souls it seated, its blood and its tongue answering from their own tiers
    "family.metadata": {"kingdoms", "parents"},  # a second crown or a parent line is too rare for a panel row, so both ride the script's output alone
    "family.ranks": {"cities", "kingdoms"},  # towns and crowns follow the heads that hold them, so the podium repeats the one `members` already draws
    # The bodies it belongs to, each read to open its own tier block — and its stock, which the portrait draws off the persons registry
    "favorite.metadata": {"asset_id", "city", "clan", "culture", "family", "kingdom", "language", "religion", "subspecies"},
    "kingdom.identity": {"clan", "culture", "language", "religion", "subspecies"},  # as a town's
    "kingdom.metadata": {"births", "ferries"},  # as a town's, and no panel asks whether a crown ferries — that answers a rule of the chronicle, not a row
    "kingdom.population": {"money"},  # as a town's
    "kingdom.ranks": {"money"},  # as a town's
    "language.identity": {"species", "subspecies"},  # the founder's stock, as a culture's
    "religion.identity": {"species", "subspecies"},  # the founder's stock, as a culture's
    "wars.metadata": {"deaths", "started_by"},  # the card sets each camp's toll and crown, never the sum or the man — `war/info.py <id>` hands over both
}

# No panel reads them: `report` and `info` are per-call, `taxonomy` comes from `identity.species`, `passengers` is the chronicler's own reading.
_CHRONICLER_ONLY = frozenset({"age_description", "age_name", "info", "passengers", "report", "sapient", "taxonomy"})

# `population` keys no panel reads — the chronicler still gets them whole from `<tier>/info.py <id> population`, they simply don't ride along in the chapter.
_DEMOGRAPHY = frozenset(
    {"adults", "babies", "children", "couples", "eggs", "elders", "familyless", "gen_deepest", "gen_median", "happy", "men", "nobles", "teens", "women"}
)

# The podium rows a panel names, mirroring `LEADER_FAMILY_ROWS`/`LEADER_PERSON_ROWS` (`stats.constant.ts`). The rest stays in `<tier>/info.py <id> leaders`.
_LEADER_ROWS = {"families": frozenset({"population"}), "persons": frozenset({"kills", "level", "money", "oldest", "renown"})}

# Rosters, libraries and fleets kept as a count alone — the tier's own `info.py <id> <section>` still names every soul, volume and hull behind the figure.
_TALLIES = {
    "clan": ("members",),
    "culture": ("books", "members"),
    "family": ("members",),
    "kingdom": ("boats",),
    "language": ("books", "members"),
    "religion": ("books", "members"),
    "subspecies": ("members",),
}

# The counters « Activité récente » prints, mirroring `CUMULATIVE_STATS` (`stats.constant.ts`), `deaths` riding along for the breakdown panel below it.
_UI_CUMULATIVE = frozenset({"books_burnt", "books_read", "cities_conquered", "cities_rebelled", "deaths", "evolutions", "metamorphosis", "plots_succeeded"})


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
    for key in ("kills", "level", "loot", "mass_kg", "renown", "speed"):  # `home`, `x` and `y` go with `_AUDIT`, which takes them from every `metadata`
        metadata.pop(key, None)


# The composition table names each dimension's leader and its share: the runners-up print nowhere, and a leader holding everyone restates its own panel.
def _fold_breakdown(entity: dict) -> None:
    block = entity.pop("breakdown", None) or {}
    if kept := {dimension: rows[:1] for dimension, rows in block.items() if rows[0]["pct"] < 100}:
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
    podium = entity.get("leaders") or {}
    for block, kept in _LEADER_ROWS.items():
        if isinstance(rows := podium.get(block), dict):
            podium[block] = {key: _first_holder(refs) for key, refs in rows.items() if key in kept}


# The age and sex slices, the lineage depth, the count of nobles — figures the chronicler writes with and no panel prints. `population` keeps what the UI reads.
def _fold_population(entity: dict) -> None:
    if isinstance(block := entity.get("population"), dict):
        entity["population"] = {k: v for k, v in block.items() if k not in _DEMOGRAPHY}


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
    (subspecies.get("species") or {}).pop("description", None)  # WB's blurb on the parent stock — narrative, and the panel never prints it


# The panels read nothing but the `total`, whichever form `full` handed over — nothing is lost, the chapter's own `map.wbox` replaying any section.
def _fold_total(entity: dict, *keys: str) -> None:
    for key in keys:
        if isinstance(block := entity.get(key), dict):
            entity[key] = {"total": block.get("total", 0)}


# Every record of the world's « Palmarès », each to its first holder — `world/info.py <chapter> leaders` naming them all.
def _fold_world_leaders(world: dict) -> None:
    if isinstance(block := world.get("leaders"), dict):
        world["leaders"] = {group: {row: _first_holder(holders) for row, holders in rows.items()} for group, rows in block.items()}


def _without(block: dict, cut: frozenset) -> dict:
    return {key: value for key, value in block.items() if key not in cut}


# `_CHRONICLER_ONLY` cuts at every depth of the tree, `_AUDIT` from one named section alone — neither loses the chronicler a thing, `<tier>/info.py` replaying both.
def drop_chronicler_keys(node, parent: str = ""):
    if isinstance(node, dict):
        kept = {}
        for key, value in node.items():
            if key in _CHRONICLER_ONLY:
                continue
            if cut := _AUDIT.get(key, frozenset()) | _AUDIT_TIERS.get(f"{parent}.{key}", frozenset()):  # a section is a dict, save `relations`, a list of them
                if isinstance(value, dict):
                    value = _without(value, cut)
                elif isinstance(value, list):
                    value = [_without(item, cut) if isinstance(item, dict) else item for item in value]
            kept[key] = drop_chronicler_keys(value, key)
        return kept
    return [drop_chronicler_keys(value, parent) for value in node] if isinstance(node, list) else node


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
        _fold_population(block)
        block.pop("traits", None)  # the raw list goes; `new.py` carries or asks for the chronicler's prose in its place
        if fold := folds.get(tier):
            fold(block)
        if keys := _TALLIES.get(tier):
            _fold_total(block, *keys)
    if boat:
        _fold_boat_detail(boat)
        _fold_total(boat, "crew")  # the panel prints how many souls are aboard, `boat/info.py <id> crew` names them


# Folds the favorite's heavy blocks: their traits, their gear, who stands around them and the scheme's detail all go — `actor/info.py <id>` still hands each whole.
def fold_favorite_detail(favorite: dict) -> None:
    for section in ("gear", "surroundings"):
        favorite.pop(section, None)
    # The panel prints the type, the target and the gauge: WB's English is the chronicler's, and so is how long the scheme has run.
    plot = favorite.get("plot") or {}
    plot.pop("months", None)
    if kind := plot.get("type"):
        plot["type"] = {"id": kind.get("id")}
    favorite.pop("traits", None)  # the chronicler's summary takes its place, carried over or owed


# The world block as its panels print it: the tallies and podiums folded, each scheme's type cut to its key.
def fold_world(world: dict) -> None:
    _fold_cumulative(world)
    _fold_world_leaders(world)
    _fold_total(world, "boats")  # counted, never listed: both panels print the count alone, `<tier>/info.py … boats` naming the hulls on demand
    for scheme in world.get("plots") or []:  # the schemer and the type's key: WB's English is the chronicler's, and the panel owns the French
        scheme["type"] = {"id": (scheme.get("type") or {}).get("id")}

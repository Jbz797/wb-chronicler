#!/usr/bin/env python3

# Builds a chapter's `<entity>.json` registries under `saves/C<n>/`, one per kind in `_REGISTRIES` — the tag visuals (+ last-known names) the UI and chronicler
# resolve an inline `[<letter> id]` marker from, crowns and banners composed on canvas. Carried forward from C<n-1> (dead kept), rebuilt whole.
# `ensure()` is what the bootstrap (`chapter/new.py`) calls; `registries.py C<n> [--force]` (re)builds one chapter standalone — a dev tool, not in `tools.md`.

import json
import sys
from collections import Counter, defaultdict
from functools import cache
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from shared import MIN_RANK_PEERS, SAVES_DIR, city_score_ranks, index_by_id, is_boat, kingdom_score_ranks, load_data, load_save, resolve_profession, sex_label

_ENCODE = json.JSONEncoder(ensure_ascii=False, sort_keys=True).encode  # mounted once: given keyword arguments, `json.dumps` builds a fresh encoder per call

# Where each tier keeps its founder(s) and the stock to draw them from — WB names the field differently on every one, and a lineage claims two.
_FOUNDER_FIELDS = (
    ("cities", ("founder_id",), "original_actor_asset"),
    ("clans", ("founder_actor_id",), "original_actor_asset"),
    ("cultures", ("creator_id",), "original_actor_asset"),
    ("families", ("main_founder_id_1", "main_founder_id_2"), "species_id"),
    ("kingdoms", ("founder_id",), "original_actor_asset"),
    ("languages", ("creator_id",), "creator_species_id"),
    ("religions", ("creator_id",), "creator_species_id"),
)

_PODIUM_PLACES = 3  # gold, silver, bronze — and the widest tie a place can hold, past which the medal marks the field, not the one who takes it
_REALM_FALLBACK_HUE = "#B0B0B0"  # WB `Toolbox.color_grey` — worn by a realm whose palette WB never shipped, the only case the name hue can miss.
_REGISTRIES = ("alliances", "books", "cities", "clans", "cultures", "families", "kingdoms", "languages", "persons", "religions", "subspecies")
_SIZE_TIERS = (5, 15, 30, 60, 120, 250, 500, 1000)  # Population upper bounds → settlement tier 1-9 (foyer→cité-monde), mirrors the `chronicler.md` naming scale.


# Alliance entry: name, hue, crown count and the founding crown's heraldry, WB giving a pact no king — no podium, no size tier, and oath binds no one stock.
def _alliance_entry(alliance: dict) -> dict:
    palette = _palette(alliance.get("color_id", ""))
    # WB `AllianceBanner.setupBanner`: its own two sprite lists, indexed by the save's ids, under `alliance_frame` — `_unity` unless `alliance_type` is normal.
    return {
        "banner_bg": alliance.get("banner_background_id") or 0,
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": alliance.get("banner_icon_id") or 0,
        "banner_icon_color": palette.get("color_banner"),
        **({"banner_unity": True} if alliance.get("alliance_type") else {}),
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue; a `null` would break the UI type
        "color_main": palette.get("color_main"),
        "kingdoms": len(alliance.get("kingdoms") or []),  # the badge in the right link: crowns bound, the one count that tells two pacts apart at a glance
        "name": alliance.get("name"),
    }


# WB `KingdomBanner.setupBanner` inputs for the UI's canvas: the slots the realm's two banner ids pick in its king's species set, each with its hue. Realms only.
def _banner(record: dict, species: str | None) -> dict:
    lib = load_data("banner-icons.json")
    banner_id = lib["species_to_banner_id"].get(species)
    bg_slots, icon_slots = lib["banner_id_backgrounds"].get(banner_id), lib["banner_id_icons"].get(banner_id)
    if not bg_slots or not icon_slots:  # species without a banner set (never seen in practice) → no fields, and the tag simply wears no heraldry
        return {}
    palette = _palette(record.get("color_id", ""))
    return {
        "banner_bg": bg_slots[i if (i := record.get("banner_background_id") or 0) < len(bg_slots) else 0],
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": icon_slots[i if (i := record.get("banner_icon_id") or 0) < len(icon_slots) else 0],
        "banner_icon_color": palette.get("color_banner"),
    }


# Book registry entry — the two sheets its sprite stacks and the hue WB prints its title in, all three read off its genre. `_merge` flags a burnt one `dead`.
def _book_entry(book: dict, genres: dict, rank: int | None) -> dict:
    genre = genres.get(book.get("book_type")) or {}
    entry = {
        "color": genre.get("color"),
        "cover": book.get("path_cover"),  # `books/book_covers/<cover>` — twenty sheets, the same set for every genre
        "icon": f"{genre.get('folder') or book.get('book_type')}/{book.get('path_icon')}",  # the glyph, white, drawn over the cover from its genre's own folder
        "name": book.get("name"),
    }
    if reads := int(book.get("times_read") or 0):  # the badge, dropped while nobody has opened it — a shelf holds many a volume no one reads
        entry["reads"] = reads
    if rank is not None:
        entry["rank"] = rank
    return _defined(entry)


# The chapter's registries: prev chapter merged with this save (live → period-accurate, gone → last-known `dead`, lost founders folded).
def _build_registries(save: dict, prev: dict) -> dict:
    actors = save.get("actors_data") or []
    cities = save.get("cities") or []
    kingdoms = save.get("kingdoms") or []
    items_by_id = index_by_id(save.get("items") or [])
    king_ids = {kid for k in kingdoms if (kid := k.get("kingID"))}  # the crowned only — a realm's banner set follows its king's species
    kingdoms_by_id = index_by_id(kingdoms)
    kings_by_id: dict = {}

    # Actor and trade, kept whole through the pass: a fiche can only take its rank once every level has been counted.
    crowd: dict[int, tuple[dict, str | None]] = {}
    subspecies_by_id = index_by_id(save.get("subspecies") or [])

    # Headcount and dominant species are all an entry needs, so tally straight away — and WB points the actor at its clan, lineage and biology, never the reverse.
    members_by_clan: Counter = Counter()
    members_by_culture: Counter = Counter()
    members_by_family: Counter = Counter()
    members_by_language: Counter = Counter()
    members_by_religion: Counter = Counter()
    members_by_subspecies: Counter = Counter()
    species_by_city: defaultdict[int, Counter] = defaultdict(Counter)
    species_by_kingdom: defaultdict[int, Counter] = defaultdict(Counter)

    for a in actors:
        if is_boat(a):
            continue
        if cid := a.get("clan"):
            members_by_clan[cid] += 1
        if cid := a.get("culture"):
            members_by_culture[cid] += 1
        if fid := a.get("family"):
            members_by_family[fid] += 1
        if lid := a.get("language"):
            members_by_language[lid] += 1
        if rid := a.get("religion"):
            members_by_religion[rid] += 1
        if sid := a.get("subspecies"):
            members_by_subspecies[sid] += 1
        actor_id, species = a["id"], a.get("asset_id")  # both read three times below
        if actor_id in king_ids:
            kings_by_id[actor_id] = a
        if (cid := a.get("cityID")) is not None:
            species_by_city[cid][species] += 1
        if kid := a.get("civ_kingdom_id"):
            species_by_kingdom[kid][species] += 1
        # Every non-boat actor, kingdomless wilds included — the chronicler may tag any of them (species exemplars, lone notables…).
        crowd[actor_id] = (a, resolve_profession(a, save))

    rank_by_person = _podium(Counter({aid: int(a.get("level") or 0) for aid, (a, _) in crowd.items()}))  # a level, where every other podium counts heads
    persons = {str(aid): _person_entry(a, job, items_by_id, subspecies_by_id, rank_by_person.get(aid)) for aid, (a, job) in crowd.items()}

    rank_by_city = {cid: rank for cid, rank in city_score_ranks(save).items() if rank <= 3}  # top-3 of the composite settlement weight → same medal as a realm's
    rank_by_kingdom = {kid: rank for kid, rank in kingdom_score_ranks(save).items() if rank <= 3}  # top-3 of the composite power score → gold/silver/bronze medal

    city_registry = {
        str(c["id"]): _city_entry(c, species_by_city.get(c["id"], Counter()), kingdoms_by_id.get(c.get("kingdomID")), rank_by_city.get(c["id"])) for c in cities
    }

    kingdom_registry = {
        str(k["id"]): _defined(
            _kingdom_entry(k, species_by_kingdom.get(k["id"], Counter()), rank_by_kingdom.get(k["id"]))
            | _banner(k, _kingdom_species(k, kings_by_id, subspecies_by_id))
        )
        for k in kingdoms
    }

    alliances = save.get("alliances") or []
    alliance_registry = {str(a["id"]): _defined(_alliance_entry(a)) for a in alliances}

    book_genres = load_data("books.json")
    rank_by_book = _podium(Counter({b["id"]: int(b.get("times_read") or 0) for b in save.get("books") or []}))  # readings alone rank a volume
    book_registry = {str(b["id"]): _book_entry(b, book_genres, rank_by_book.get(b["id"])) for b in save.get("books") or []}

    rank_by_clan = _podium(members_by_clan)  # the sworn alone rank a band, as followers rank a custom
    clan_registry = {str(c["id"]): _clan_entry(c, members_by_clan.get(c["id"], 0), rank_by_clan.get(c["id"])) for c in save.get("clans") or []}

    rank_by_culture = _podium(members_by_culture)  # followers alone rank a culture, where a settlement and a realm each take a composite score
    culture_registry = {str(c["id"]): _culture_entry(c, members_by_culture.get(c["id"], 0), rank_by_culture.get(c["id"])) for c in save.get("cultures") or []}

    rank_by_family = _podium(members_by_family)  # the living who carry the name, as the sworn rank a band
    family_registry = {str(f["id"]): _family_entry(f, members_by_family.get(f["id"], 0), rank_by_family.get(f["id"])) for f in save.get("families") or []}

    rank_by_language = _podium(members_by_language)  # speakers alone rank a tongue, as followers rank a custom
    language_registry = {str(t["id"]): _language_entry(t, members_by_language.get(t["id"], 0), rank_by_language.get(t["id"])) for t in save.get("languages") or []}

    rank_by_religion = _podium(members_by_religion)  # the faithful alone rank a creed, as followers rank a custom
    religion_registry = {str(r["id"]): _religion_entry(r, members_by_religion.get(r["id"], 0), rank_by_religion.get(r["id"])) for r in save.get("religions") or []}

    rank_by_subspecies = _podium(members_by_subspecies)  # the living bearers, as the sworn rank a band
    subspecies_registry = {
        str(s["id"]): _subspecies_entry(s, members_by_subspecies.get(s["id"], 0), rank_by_subspecies.get(s["id"])) for s in save.get("subspecies") or []
    }

    out = {
        "alliances": _merge(prev.get("alliances") or {}, alliance_registry),
        "books": _merge(prev.get("books") or {}, book_registry),
        "cities": _merge(prev.get("cities") or {}, city_registry),
        "clans": _merge(prev.get("clans") or {}, clan_registry),
        "cultures": _merge(prev.get("cultures") or {}, culture_registry),
        "families": _merge(prev.get("families") or {}, family_registry),
        "kingdoms": _merge(prev.get("kingdoms") or {}, kingdom_registry),
        "languages": _merge(prev.get("languages") or {}, language_registry),
        "persons": _merge(prev.get("persons") or {}, persons),
        "religions": _merge(prev.get("religions") or {}, religion_registry),
        "subspecies": _merge(prev.get("subspecies") or {}, subspecies_registry),
    }

    # A founder dead before the first chapter was archived sits in no registry, so its tag would resolve to nothing — its tier's `species` draws it instead.
    for tier, id_fields, asset_field in _FOUNDER_FIELDS:
        for record in save.get(tier) or []:
            asset = record.get(asset_field)
            rulers = record.get("past_rulers") or []
            for fid in (*(record.get(f) for f in id_fields), rulers[0].get("id") if rulers else None):
                if fid and asset and str(fid) not in out["persons"]:
                    out["persons"][str(fid)] = {"asset_id": asset, "dead": True}

    return out


# City registry entry — what a `[c id Nom]` tag draws, plus the last-known name. `kingdom` stands in for the name's hue, all it still borrows from its crown.
def _city_entry(city: dict, species: Counter, kingdom: dict | None, rank: int | None) -> dict:
    dominant = species.most_common(1)
    kingdom = kingdom or {}
    entry = {
        "name": city.get("name"),
        "plate": "capital" if kingdom.get("capitalID") == city.get("id") else "city",  # WB's nameplates: gold studs mark a seat, bare stone the rest
        "species": dominant[0][0] if dominant else None,
    }
    if kingdom_id := kingdom.get("id"):  # its crown, which the name's hue is read off — fallen realms stay registered so a razed city keeps its colour
        entry["kingdom"] = kingdom_id
    if rank is not None:
        entry["rank"] = rank
    if (size := _size_tier(species.total())) > 1:  # a medallion reading `1` states the floor — every tag pill stays silent at its lowest tier
        entry["size"] = size
    return _defined(entry)


# Clan registry entry — its own hue (a clan is sworn, not granted, so it carries no crown's colour), the founder's species and the living headcount.
def _clan_entry(clan: dict, members: int, rank: int | None) -> dict:
    palette = _palette(clan.get("color_id", ""))
    entry: dict = {
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue; a `null` would break the UI type
        "name": clan.get("name"),
        "species": clan.get("creator_species_id"),  # the founder's stock, which its recruits need not share — the pip right of the name
    }
    if (size := _size_tier(members)) > 1:  # every tag pill stays silent at its lowest tier, as the city medallion does
        entry["size"] = size
    if rank is not None:
        entry["rank"] = rank
    entry |= {  # WB gives clans their own sheets (`clan_background_*`, `clan_icon_*`), indexed straight by these two ids — not the realms' species-keyed sets.
        "banner_bg": clan.get("banner_background_id") or 0,
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": clan.get("banner_icon_id") or 0,
        "banner_icon_color": palette.get("color_banner"),
    }
    return _defined(entry)


# Culture registry entry — its own hue (a custom is caught, not granted, so it wears no crown's colour), the founder's species and the living headcount.
def _culture_entry(culture: dict, followers: int, rank: int | None) -> dict:
    palette = _palette(culture.get("color_id", ""))
    entry: dict = {
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue; a `null` would break the UI type
        "name": culture.get("name"),
        "species": culture.get("creator_species_id"),  # the founder's stock, which those raised in it need not share — the pip right of the name
    }
    if (size := _size_tier(followers)) > 1:
        entry["size"] = size
    if rank is not None:
        entry["rank"] = rank
    entry |= {  # WB `CultureBanner.setupBanner`: field and border take `color_main_2`, the motif `color_banner` — a clan's splits the same roles.
        "banner_bg": culture.get("banner_decor_id") or 0,
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": culture.get("banner_element_id") or 0,
        "banner_icon_color": palette.get("color_banner"),
    }
    return _defined(entry)


# Absence carried as absence: a razed town has no dominant species, a paletteless realm no `color_main` — and UI-side a `null` would read as a value.
def _defined(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if value is not None}


# Family registry entry — the frame the tag wears as a border, the founding species' pip, the flattened backing hue and the living headcount, plus the last name.
def _family_entry(family: dict, members: int, rank: int | None) -> dict:
    entry = {
        "frame": family.get("banner_frame_id") or 0,  # an absent banner id arrives as C#'s 0 — slot zero, not no slot
        "name": family.get("name"),
    }
    if (size := _size_tier(members)) > 1:  # a lineage carried over from an older chapter keeps none, as every tag pill stays silent at its lowest tier
        entry["size"] = size
    if rank is not None:
        entry["rank"] = rank
    if (species := family.get("species_id")) is not None:  # the founding species' pip, right of the name as on every other tag
        entry["species"] = species
    # WB paints the backing sprite with `getColorMainSecond` (families borrow the realms' palette). Flattened to one hex: the tag fills rather than stacks.
    backing = load_data("colors.json")["family_frames"].get(f"{family.get('banner_background_id') or 0:02}")
    tint = _palette(family.get("color_id", "")).get("color_main_2") or _REALM_FALLBACK_HUE  # WB grants a handful of lineages no palette at all — grey, as it does
    if backing:
        entry["bg_color"] = _multiply(backing, tint)
    return _defined(entry)


# Kingdom entry, less the heraldry `_banner` folds in and the merge's `dead`. It alone holds a hue — cities and subjects read theirs off it.
def _kingdom_entry(kingdom: dict, species: Counter, rank: int | None) -> dict:
    dominant, palette = species.most_common(1), _palette(kingdom.get("color_id", ""))
    entry: dict = {
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue, and the magenta ramp root once lightened; a `null` would break the UI type
        "color_main": palette.get("color_main"),
        "name": kingdom.get("name"),
        "species": dominant[0][0] if dominant else None,
    }
    if (size := _size_tier(species.total())) > 1:  # the crown's own people, not its towns: the chronicler reads those from `kingdom/info.py`
        entry["size"] = size
    if rank is not None:
        entry["rank"] = rank
    return entry


# The king's (or founder's) species — drives the banner set: living subspecies → its `species_id`, else the founding `original_actor_asset` (dead-founder fallback).
def _kingdom_species(kingdom: dict, kings_by_id: dict, subspecies_by_id: dict) -> str | None:
    king = kings_by_id.get(kingdom.get("kingID"))
    subspecies = subspecies_by_id.get(king.get("subspecies")) if king else None
    return (subspecies or {}).get("species_id") or kingdom.get("original_actor_asset")


# Language registry entry — its own hue (a tongue is caught, not granted, so it wears no crown's colour), the founder's species and the living headcount.
def _language_entry(language: dict, speakers: int, rank: int | None) -> dict:
    palette = _palette(language.get("color_id", ""))
    entry: dict = {
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue; a `null` would break the UI type
        "name": language.get("name"),
        "species": language.get("creator_species_id"),  # the founder's stock, which those who answer in it need not share — the pip right of the name
    }
    if rank is not None:
        entry["rank"] = rank
    if (size := _size_tier(speakers)) > 1:
        entry["size"] = size
    entry |= {  # WB `LanguageBanner.setupBanner`: ten parchment fields and twenty-one scripts of its own, indexed straight by these two ids.
        "banner_bg": language.get("banner_background_id") or 0,
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": language.get("banner_icon_id") or 0,
        "banner_icon_color": palette.get("color_banner"),
    }
    return _defined(entry)


def _load_registries(chapter_dir: Path) -> dict:
    return {name: json.loads(p.read_text()) if (p := chapter_dir / f"{name}.json").exists() else {} for name in _REGISTRIES}


# Prior entries carried forward flagged dead (last-known visuals kept), bar those still alive — a living entity rewrites its own. `rank` and the headcounts go.
def _merge(prev: dict, live: dict) -> dict:
    carried = {}
    for entry_key, entry in prev.items():  # spread then pop beats filtering the items — most entries never held either key
        if entry_key in live:
            continue
        carried[entry_key] = fallen = {**entry, "dead": True}
        for volatile in ("kingdoms", "rank", "size"):  # the tier, the medal and the crowns of the living, none of which a last-known entry has a claim to
            fallen.pop(volatile, None)
    return carried | live


# Unity's `set_color` is a multiply — the flat fill a tinted backing comes out as.
def _multiply(base: str, tint: str) -> str:
    channels = (int(base[i : i + 2], 16) * int(tint[i : i + 2], 16) // 255 for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*channels)


# A realm's palette, verbatim — WB's own `checkIfColorTooDark` belongs to the sprite ramps alone, so the UI applies it. Empty when WB shipped no such palette.
@cache  # realms of one palette share the call, and every chapter rebuild replays it
def _palette(color_id) -> dict:
    return load_data("colors.json")["entities"].get(str(color_id), {})


# Person registry entry — everything the UI composes an actor from, plus the last-known name. `dead` comes from the merge.
def _person_entry(actor: dict, profession: str | None, items_by_id: dict, subspecies_by_id: dict, rank: int | None) -> dict:
    carried = [(items_by_id.get(iid) or {}).get("asset_id", "") for iid in actor.get("saved_items") or []]  # resolved once: head and weapon both read it
    entry = {"asset_id": actor.get("asset_id"), "sex": sex_label(actor)}
    for field in ("head", "phenotype_index", "phenotype_shade"):  # All three default to 0 in WB — omit then, the reader falls back to the same.
        if value := actor.get(field):
            entry[field] = value
    if profession and profession != "civilian":  # a civilian carries no badge — keep the registry lean.
        entry["job"] = profession
    if kingdom := actor.get("civ_kingdom_id"):  # Their realm's hue dyes the clothes — kept as a ref so the palette lives in one place, the kingdom registry.
        entry["kingdom"] = kingdom
    if (level := max(int(actor.get("level") or 0), 1)) > 1:  # most of a world sits at 1 — a medallion on every subject would say nothing, so it stays earned
        entry["level"] = level
    if rank is not None:
        entry["rank"] = rank
    if name := actor.get("name"):  # Plenty of actors are unnamed — omit rather than store a placeholder; the tag's inline name stays the fallback.
        entry["name"] = name
    if skin := (subspecies_by_id.get(actor.get("subspecies")) or {}).get("skin_id"):  # WB `Subspecies.cacheSkins` picks the body sheet; absent means index 0.
        entry["skin_id"] = skin
    if special := _special_head(actor, profession, carried):
        entry["special_head"] = special
    if carried and (weapon := _wielded_weapon(carried)):  # half the world carries nothing at all, and an empty hand needs no lookup through the weapon set
        entry["weapon"] = weapon
    return entry


# Competition ranks (1, 2, 2, 4) over three places, `{}` where the medal says nothing — too thin a field, or a tie so wide that gold marks the world, not the winner.
def _podium(counts: Counter) -> dict[int, int]:
    if len(counts) < MIN_RANK_PEERS:
        return {}
    ranks: dict[int, int] = {}
    place = 1
    for _, group in groupby(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])), key=lambda kv: kv[1]):
        if place > _PODIUM_PLACES:
            break
        tied = [entity_id for entity_id, _ in group]
        if len(tied) <= _PODIUM_PLACES:  # skipped, not stopped: the places they fill still push the next value down the board
            ranks.update(dict.fromkeys(tied, place))
        place += len(tied)
    return ranks


# Religion registry entry — its own hue (a creed is preached, not granted, so it wears no crown's colour), the founder's species and the living headcount.
def _religion_entry(religion: dict, faithful: int, rank: int | None) -> dict:
    palette = _palette(religion.get("color_id", ""))
    entry: dict = {
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue; a `null` would break the UI type
        "name": religion.get("name"),
        "species": religion.get("creator_species_id"),  # the founder's stock, which those who hold to it need not share — the pip right of the name
    }
    if (size := _size_tier(faithful)) > 1:
        entry["size"] = size
    if rank is not None:
        entry["rank"] = rank
    entry |= {  # WB `ReligionBanner.setupBanner`: five fields and twenty-five signs of its own, indexed straight by these two ids.
        "banner_bg": religion.get("banner_background_id") or 0,
        "banner_bg_color": palette.get("color_main_2"),
        "banner_icon": religion.get("banner_icon_id") or 0,
        "banner_icon_color": palette.get("color_banner"),
    }
    return _defined(entry)


# Population tier 1-9 — mirrors the `chronicler.md` naming scale (foyer → cité-monde). Drives the Civ-style badge every tag wears but the person's.
def _size_tier(population: int) -> int:
    return next((tier for tier, cap in enumerate(_SIZE_TIERS, start=1) if population <= cap), len(_SIZE_TIERS) + 1)


# WB `Actor.checkSpriteHead`: a worn helmet, then a crown, then the white hair of the wise — each replaces the drawn head; failing all three, `head` picks it.
def _special_head(actor: dict, profession: str | None, carried: list[str]) -> str | None:
    if profession in ("army_captain", "warrior") and any(asset.startswith("helmet_") for asset in carried):
        return "head_warrior"
    if profession == "king":
        return "head_king"
    return "head_old" if "wise" in (actor.get("saved_traits") or []) else None


# Subspecies registry entry — the stone slab it is written on, the two bookmark hues WB dyes over it, the species pip and the last-known name.
def _subspecies_entry(subspecies: dict, members: int, rank: int | None) -> dict:
    palette = _palette(subspecies.get("color_id", ""))
    entry = {
        "banner_bg": subspecies.get("banner_background_id") or 0,  # WB `SubspeciesBannerLibrary`: twelve slabs of its own, not the 272 a crown draws from.
        "color": palette.get("color_text") or _REALM_FALLBACK_HUE,  # the name hue; a `null` would break the UI type
        "color_main": palette.get("color_main"),  # `getColorMain`, dyeing the inner bookmark
        "color_main_2": palette.get("color_main_2"),  # `getColorMainSecond`, dyeing the outer one
        "name": subspecies.get("name"),
        "species": subspecies.get("species_id"),  # the stock WB mutated it out of — the pip right of the name
    }
    if (size := _size_tier(members)) > 1:
        entry["size"] = size
    if rank is not None:
        entry["rank"] = rank
    return _defined(entry)


# Wieldable item asset_ids — `damage` is what tells a weapon from armor in `equipment.json`; the eight boat projectiles that share it never sit in an inventory.
@cache
def _weapon_assets() -> frozenset[str]:
    return frozenset(asset for asset, entry in load_data("equipment.json")["items"].items() if "damage" in entry["stats"])


# The weapon an actor holds — WB gives out at most one, so the first match is it.
def _wielded_weapon(carried: list[str]) -> str | None:
    assets = _weapon_assets()
    return next((asset for asset in carried if asset in assets), None)


# One line per entry, sorted by numeric id with fields alphabetical, so a changed entry shows up as a one-line diff rather than a reshuffled block.
def _write_registry(path: Path, registry: dict) -> None:
    # One dump per entry, not per field, and `sort_keys` rather than a pre-sorted copy — both push the work into C. Keys are ids, so they need no escaping.
    rows = [f'  "{entry_key}": {{ {_ENCODE(entry)[1:-1]} }}' for entry_key, entry in sorted(registry.items(), key=lambda item: int(item[0]))]
    path.write_text("{\n" + ",\n".join(rows) + "\n}\n")


# Builds this chapter's registries when missing (idempotent). Recurses to carry C<n-1> forward first, so the dead persist chapter to chapter.
def ensure(chapter: str, save: dict | None = None) -> None:
    chapter_dir = SAVES_DIR / chapter
    if all((chapter_dir / f"{name}.json").exists() for name in _REGISTRIES):
        return
    n = int(chapter[1:])
    prev = {}
    if n > 1:
        ensure(f"C{n - 1}")
        prev = _load_registries(SAVES_DIR / f"C{n - 1}")
    if save is None:  # the bootstrap already holds this chapter's save — reloading it would cost a full re-parse
        save = load_save(chapter_dir / "map.wbox")
    for name, registry in _build_registries(save, prev).items():
        _write_registry(chapter_dir / f"{name}.json", registry)


def main(argv: list[str]) -> int:
    chapter = next((a for a in argv if a.startswith("C") and a[1:].isdigit()), None)
    if chapter is None:
        print("usage: registries.py C<n> [--force] — (re)builds the saves/C<n>/ registries", file=sys.stderr)
        return 2
    if "--force" in argv:  # clear first so `ensure` rebuilds from scratch (e.g. after a py change to an entry's shape)
        for name in _REGISTRIES:
            (SAVES_DIR / chapter / f"{name}.json").unlink(missing_ok=True)
    # Asked before the call, since `ensure` is idempotent and silent: without this, a build and a no-op would look exactly alike from the terminal.
    fresh = not all((SAVES_DIR / chapter / f"{name}.json").exists() for name in _REGISTRIES)
    ensure(chapter)
    counts = " · ".join(f"{len(json.loads((SAVES_DIR / chapter / f'{name}.json').read_text()))} {name}" for name in _REGISTRIES)
    print(f"✓ {chapter} registries {'built' if fresh else 'already in place'} — {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

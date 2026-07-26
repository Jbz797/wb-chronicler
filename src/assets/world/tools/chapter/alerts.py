# World-law alerts: data-checkable conditions on the save. When one first holds, `chapter/new.py` tags the chapter and surfaces its message — once ever, since it
# de-dups against the prior chapters' tags. Adding an alert = a new entry below. Chronicler reference: `history/tags.md`.

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import is_boat, load_data

# code → {condition(kingdoms, present), message}; from `_analyze`: `kingdoms` = {playable species: [pops]} keyed by dominant, `present` = those with living actors.
_ALERTS = {
    "DISABLE_DROP_OF_THOUGHTS": {
        "condition": lambda kingdoms, present: all(kingdoms.get(species) for species in present),
        "message": "Tu peux désactiver la loi de monde Drop of Thoughts.",
    },
    "DISABLE_HANDSOME_MIGRANTS": {
        "condition": lambda kingdoms, present: all(any(pop >= _MIN_KINGDOM_POP for pop in kingdoms.get(species, ())) for species in present),
        "message": "Tu peux désactiver la loi de monde Handsome Migrants.",
    },
}
_MIN_KINGDOM_POP = 4  # `DISABLE_HANDSOME_MIGRANTS` threshold — a kingdom of ≥ 4 inhabitants.


# Playable species present in the world (species.json `playable` flag) + {species: [kingdom populations]} keyed by each kingdom's dominant playable species.
def _analyze(save: dict) -> tuple[dict, set]:
    playable = {species for species, data in load_data("species.json").items() if data.get("playable")}
    members_by_kingdom: dict[int, Counter] = {}
    species_seen: set = set()

    for actor in save.get("actors_data") or []:  # one pass gives both which species walk the world and each kingdom's species mix
        if is_boat(actor):
            continue
        asset = actor.get("asset_id")
        species_seen.add(asset)
        if kid := actor.get("civ_kingdom_id"):
            members_by_kingdom.setdefault(kid, Counter())[asset] += 1
    kingdoms: dict = {}

    for members in members_by_kingdom.values():
        if (dominant := members.most_common(1)[0][0]) in playable:
            kingdoms.setdefault(dominant, []).append(members.total())

    return kingdoms, species_seen & playable


# `(code, message)` of alerts whose condition holds now and that haven't fired yet (`already` = tags already set in prior chapters).
def fired(save: dict, already: set) -> list[tuple[str, str]]:
    kingdoms, present = _analyze(save)
    if not present:  # no playable species yet → every `all(...)` would hold vacuously
        return []
    return [(code, spec["message"]) for code, spec in _ALERTS.items() if code not in already and spec["condition"](kingdoms, present)]

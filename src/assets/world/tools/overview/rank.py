#!/usr/bin/env python3
"""Rank an actor on every stat among all individuals of the same species.

Usage: python3 rank.py <id>

Reads the live save (cf. `stats.CURRENT_SAVE`). Aggregates the full stat dict (cf. `stats.py`)
for the actor and for every other individual sharing the same `asset_id` (species), then
derives the actor's rank per stat — `#1` is the highest value. Ties share a rank, next
rank skips (standard competition ranking: 1,2,2,4).

Only the stats present on the actor (non-zero) are ranked; peers missing a stat count as 0.

Output: `id | ranks` — `<stat>=<rank>,...` alphabetical.
"""
import json
import sys
import zlib

import stats as S


def compute_stats(actor: dict, ctx: dict) -> dict:
    # Per-subspecies cache: species template + chromosomes + subspecies traits are identical for
    # every actor sharing a subspecies, and `add_chromosome_stats` is the hottest call in the
    # pipeline. A species can host several subspecies — the cache collapses the heavy base
    # computation from one per peer to one per unique subspecies.
    sub_id = actor.get('subspecies')
    if sub_id is None or sub_id not in ctx['subspecies_by_id']: return {}
    base = ctx['subspecies_base_cache'].get(sub_id)
    if base is None:
        sub = ctx['subspecies_by_id'][sub_id]
        base = {}
        S.add_species_stats(base, ctx['asset_id'], ctx['species_data'])
        S.add_chromosome_stats(base, sub, ctx['life_dna'])
        S.add_trait_stats(base, sub.get('saved_traits') or [], ctx['subspecies_traits'])
        ctx['subspecies_base_cache'][sub_id] = base
    t = dict(base)
    S.add_trait_stats(t, actor.get('saved_traits') or [], ctx['creature_traits'])
    S.add_equipment_stats(t, actor.get('saved_items') or [], ctx['items_by_id'], ctx['equipment']['items'], ctx['equipment']['modifiers'])
    S.apply_level_scaling(t, int(actor.get('level') or 0))
    return S.cleanup(t)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try: actor_id = int(argv[0])
    except ValueError:
        print(f'invalid id: {argv[0]}', file=sys.stderr)
        return 1
    if not S.CURRENT_SAVE.exists():
        print(f'no save found at {S.CURRENT_SAVE}', file=sys.stderr)
        return 2
    with S.CURRENT_SAVE.open('rb') as f:
        save = json.loads(zlib.decompress(f.read()))
    actor = next((a for a in save['actors_data'] if a.get('id') == actor_id), None)
    if actor is None:
        print(f'unknown actor: {actor_id}', file=sys.stderr)
        return 1
    asset_id = actor.get('asset_id', '')
    ctx = {
        'asset_id':              asset_id,
        'creature_traits':       json.load(S.CREATURE_TRAITS_DATA.open()),
        'equipment':             json.load(S.EQUIPMENT_DATA.open()),
        'items_by_id':           {it['id']: it for it in save['items']},
        'life_dna':              int(save['mapStats'].get('life_dna') or 0),
        'species_data':          json.load(S.SPECIES_DATA.open()),
        'subspecies_base_cache': {},
        'subspecies_by_id':      {s['id']: s for s in save.get('subspecies', [])},
        'subspecies_traits':     json.load(S.SUBSPECIES_TRAITS_DATA.open()),
    }

    # Compute the full stats dict once per peer (favorite included). Peers without that stat = 0.
    peers = [(a['id'], compute_stats(a, ctx)) for a in save['actors_data'] if a.get('asset_id') == asset_id]
    fav_stats = next(s for aid, s in peers if aid == actor_id)

    # Standard competition rank for each of the favorite's non-zero stats.
    ranks = {stat: sum(1 for _, s in peers if s.get(stat, 0) > value) + 1 for stat, value in fav_stats.items()}
    ranks_str = ','.join(f'{k}={v}' for k, v in sorted(ranks.items()))
    print(f"{actor_id} | {ranks_str}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

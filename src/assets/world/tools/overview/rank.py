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
import sys

import stats as S


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
    save = S.load_save()
    actor = next((a for a in save['actors_data'] if a.get('id') == actor_id), None)
    if actor is None:
        print(f'unknown actor: {actor_id}', file=sys.stderr)
        return 1
    asset_id = actor.get('asset_id', '')
    ctx = S.build_context(save)

    # Subspecies-keyed cache: species template + chromosomes + subspecies traits are identical
    # across actors sharing a subspecies. Reusing the heavy base collapses ~5× of the compute
    # when many peers share one subspecies (e.g. 100+ dwarves of a single subspecies).
    cache: dict = {}
    peers = [(a['id'], S.compute_actor_stats(a, ctx, cache)) for a in save['actors_data'] if a.get('asset_id') == asset_id]
    fav_stats = next(s for aid, s in peers if aid == actor_id)

    # Standard competition rank for each of the favorite's non-zero stats.
    ranks = {stat: sum(1 for _, s in peers if s.get(stat, 0) > value) + 1 for stat, value in fav_stats.items()}
    ranks_str = ','.join(f'{k}={v}' for k, v in sorted(ranks.items()))
    print(f"{actor_id} | {ranks_str}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

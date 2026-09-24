import { CUMULATIVE_STATS, DEATH_CAUSES, SNAPSHOT_STATS } from '../constants';
import { SnapshotRow, World } from '../interfaces';

// What the « Monde » panel shows of a chapter against the one before — shared by the panel and by the overview, which hides the panel when none of it has anything.
export class WorldHelpers {

  // « Activité récente » rows: cumulative deltas, kept above zero — the schemes afoot have their own list.
  public static activityRows = (world: World, previous: World | undefined): { icon: string; label: string; value: number }[] => CUMULATIVE_STATS
    .map(({ key, label }) => ({ icon: key, label, value: (world.cumulative?.[key] ?? 0) - (previous?.cumulative?.[key] ?? 0) }))
    .filter(row => row.value > 0);

  // Per-cause death delta vs the previous chapter — `chapter.json` omits 0-counts, so a missing key reads 0. `null` on a world that never counted a death.
  public static deathsSince(world: World, previous: World | undefined): Record<string, number> | null {
    const current = world.cumulative?.deaths;
    if (!current) return null;
    const before = previous?.cumulative?.deaths;
    return Object.fromEntries(DEATH_CAUSES.map(({ key }) => [key, (current[key] ?? 0) - (before?.[key] ?? 0)]));
  }

  // Whether the panel has anything to say: a count or its change, a new event, a death, a scheme afoot, or a record held.
  public static hasContent(world: World, previous: World | undefined): boolean {
    const hasDeaths = Object.values(this.deathsSince(world, previous) ?? {}).some(n => n > 0);
    const hasRecords = Object.values(world.leaders ?? {}).some(group => Object.keys(group).length > 0);
    const hasRows = this.snapshotRows(world, previous).length > 0 || this.activityRows(world, previous).length > 0;
    return hasRows || hasDeaths || hasRecords || !!world.plots?.length;
  }

  // The world's counts with their change — `snapshot` bar the hulls, which own a block; a count at 0 left out unless it just fell there, which the delta carries.
  public static snapshotRows(world: World, previous: World | undefined): SnapshotRow[] {
    // `chapter.json` drops a zero count, so an absent one reads as 0 on either side.
    const rows: SnapshotRow[] = SNAPSHOT_STATS.map(({ icon, key, label, suffix }) => {
      const value = world.snapshot?.[key] ?? 0;
      return { delta: previous ? value - (previous.snapshot?.[key] ?? 0) : undefined, icon, key, label, suffix, value };
    });
    const boats = world.boats?.total ?? 0;
    rows.push({ delta: previous && boats - (previous.boats?.total ?? 0), icon: undefined, key: 'boats', label: 'ui_boats', suffix: undefined, value: boats });
    return rows.filter(row => row.value > 0 || !!row.delta);
  }

}

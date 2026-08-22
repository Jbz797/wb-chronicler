import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { ANONYMOUS_NAME, CUMULATIVE_STATS, DEATH_CAUSES, LEADERS, SNAPSHOT_STATS } from '../../../../constants';
import { LeaderRow } from '../../../../interfaces';
import { CompactPipe, ExactPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { DeltaComponent } from '../../../misc';

import { LeaderRowComponent } from './leader-row/leader-row.component';
import { WorldPlotsComponent } from './world-plots/world-plots.component';

@Component({
  selector: 'app-world-stats',
  imports: [CompactPipe, DeltaComponent, ExactPipe, LeaderRowComponent, NzDescriptionsModule, WorldPlotsComponent],
  templateUrl: './world-stats.component.html',
})
export class WorldStatsComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly cumulativeStats = CUMULATIVE_STATS;
  protected readonly deathCauses = DEATH_CAUSES;
  protected readonly leaders = LEADERS;
  protected readonly snapshotStats = SNAPSHOT_STATS;

  protected currentChapter = this._chronicler.currentChapter;

  // « Activité récente » rows: cumulative deltas, kept above zero — the schemes afoot have their own list below.
  protected readonly activityRows = computed<{ icon: string; label: string; value: number }[]>(() => {
    const current = this.currentChapter()?.meta.world;
    if (!current) return [];
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative;
    const rows: { icon: string; label: string; value: number }[] = this.cumulativeStats
      .map(({ key, label }) => ({ icon: key, label, value: (current.cumulative[key] ?? 0) - (previous?.[key] ?? 0) }))
      .filter(r => r.value > 0);
    return rows;
  });
  // Per-cause death delta vs previous chapter — Python omits 0-counts, so missing keys default to 0.
  protected readonly deathsSincePrevious = computed(() => {
    const current = this.currentChapter()?.meta.world.cumulative.deaths;
    if (!current) return null;
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative.deaths;
    return Object.fromEntries(this.deathCauses.map(({ key }) => [key, (current[key] ?? 0) - (previous?.[key] ?? 0)]));
  });
  // Flattened leader rows ready for the template — only present entries, each tagged with `isNew` when the top entity changed since the previous chapter.
  protected readonly leaderRows = computed<{ data: LeaderRow; icon: string; label: string }[]>(() => {
    const current = this.currentChapter()?.meta.world.leaders;
    if (!current) return [];
    const previous = this._chronicler.previousChapter()?.meta.world.leaders;
    return this.leaders.flatMap(({ icon, key, label }) => {
      const entry = current[key];
      if (!entry) return [];
      const p = previous?.[key];
      const isNew = !!previous && !!p && (entry.id !== p.id);
      // Only `most_renowned_person` can reach here unnamed; every other entity row and the dominant traits always carry one.
      return [{ data: { ...entry, isNew, key, name: entry.name ?? ANONYMOUS_NAME }, icon: icon ?? key, label }];
    });
  });
  // Rows resolved here rather than in the template: every count sits under `snapshot`, except the hulls, which own a block so the chronicler can list them.
  protected readonly snapshotRows = computed<{ delta: number | undefined; key: string; label: string; value: number }[]>(() => {
    const world = this.currentChapter()?.meta.world;
    if (!world) return [];
    const before = this._chronicler.previousChapter()?.meta.world;
    // `infected` is omitted at 0 (outbreak-style), so an absent count reads as 0 on either side.
    const rows: { delta: number | undefined; hideIfZero: boolean | undefined; key: string; label: string; value: number }[] = this.snapshotStats.map(
      ({ hideIfZero, key, label }) => {
        const value = world.snapshot[key] ?? 0;
        return { delta: before ? value - (before.snapshot[key] ?? 0) : undefined, hideIfZero, key, label, value };
      },
    );
    const boats = world.boats.total;
    rows.push({ delta: before ? boats - before.boats.total : undefined, hideIfZero: true, key: 'boats', label: 'Bateaux', value: boats });
    return rows.filter(r => !r.hideIfZero || r.value > 0).map(({ delta, key, label, value }) => ({ delta, key, label, value }));
  });
  // Causes with > 0 deaths this chapter, sorted by count desc — 0-rows are hidden (16 categories incl. peste/poison/etc. that stay idle most chapters).
  protected readonly sortedDeathCauses = computed(() => {
    const counts = this.deathsSincePrevious();
    if (!counts) return [];
    return this.deathCauses.filter(c => (counts[c.key] ?? 0) > 0).toSorted((a, b) => (counts[b.key] ?? 0) - (counts[a.key] ?? 0));
  });
  // Sum of per-cause death counts since previous chapter — `null` mirrors `deathsSincePrevious`.
  protected readonly totalDeathsSincePrevious = computed(() => {
    const breakdown = this.deathsSincePrevious();
    return breakdown ? Object.values(breakdown).reduce((sum, v) => sum + v, 0) : null;
  });

}

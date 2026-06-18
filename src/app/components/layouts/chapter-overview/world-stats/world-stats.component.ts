import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { CUMULATIVE_STATS, DEATH_CAUSES, LEADERS, SNAPSHOT_STATS } from '../../../../constants';
import { LeaderRow } from '../../../../interfaces';
import { CompactPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { DeltaComponent } from '../../../misc';

import { LeaderRowComponent } from './leader-row/leader-row.component';

@Component({
  selector: 'app-world-stats',
  imports: [CompactPipe, DeltaComponent, LeaderRowComponent, NzDescriptionsModule],
  templateUrl: './world-stats.component.html',
})
export class WorldStatsComponent {

  protected readonly cumulativeStats = CUMULATIVE_STATS;
  protected readonly deathCauses = DEATH_CAUSES;
  protected readonly leaders = LEADERS;
  protected readonly snapshotStats = SNAPSHOT_STATS;

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Per-cumulative-stat delta vs previous chapter — at C1 the baseline is 0 so we get the cumulative count instead.
  protected readonly cumulativeDeltas = computed(() => {
    const current = this.currentChapter()?.meta.world.cumulative;
    if (!current) return null;
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative;
    return Object.fromEntries(this.cumulativeStats.map(({ key }) => [key, current[key] - (previous?.[key] ?? 0)]));
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
      return [{ data: { ...entry, isNew, key }, icon: icon ?? key, label }];
    });
  });
  // Per-snapshot-stat delta vs previous chapter — `null` when no previous chapter to compare.
  protected readonly snapshotDeltas = computed(() => {
    const current = this.currentChapter()?.meta.world.snapshot;
    const previous = this._chronicler.previousChapter()?.meta.world.snapshot;
    if (!current || !previous) return null;
    return Object.fromEntries(this.snapshotStats.map(({ key }) => [key, current[key] - previous[key]]));
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

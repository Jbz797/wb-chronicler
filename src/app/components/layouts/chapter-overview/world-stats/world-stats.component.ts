import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { DeltaComponent } from '..';
import { CUMULATIVE_STATS, DEATH_CAUSES, LEADER_GROUPS, LEADER_MEASURES, SNAPSHOT_STATS } from '../../../../constants';
import { LeaderGroup, LeaderMeasure, LeaderRow, SnapshotRow } from '../../../../interfaces';
import { CompactPipe, ExactPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';

import { LeaderTableComponent } from './leader-table/leader-table.component';
import { WorldPlotsComponent } from './world-plots/world-plots.component';

@Component({
  selector: 'app-world-stats',
  imports: [CompactPipe, DeltaComponent, ExactPipe, LeaderTableComponent, NzDescriptionsModule, NzTooltipModule, TranslatePipe, WorldPlotsComponent],
  templateUrl: './world-stats.component.html',
})
export class WorldStatsComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _translate = inject(TranslateService);

  protected readonly cumulativeStats = CUMULATIVE_STATS;
  protected readonly deathCauses = DEATH_CAUSES;
  protected readonly snapshotStats = SNAPSHOT_STATS;

  protected currentChapter = this._chronicler.currentChapter;

  // « Activité récente » rows: cumulative deltas, kept above zero — the schemes afoot have their own list below.
  protected readonly activityRows = computed<{ icon: string; label: string; value: number }[]>(() => {
    const current = this.currentChapter()?.meta.world;
    if (!current) return [];
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative;
    const rows: { icon: string; label: string; value: number }[] = this.cumulativeStats
      .map(({ key, label }) => ({ icon: key, label, value: (current.cumulative?.[key] ?? 0) - (previous?.[key] ?? 0) }))
      .filter(r => r.value > 0);
    return rows;
  });
  // Per-cause death delta vs previous chapter — Python omits 0-counts, so missing keys default to 0.
  protected readonly deathsSincePrevious = computed(() => {
    const current = this.currentChapter()?.meta.world.cumulative?.deaths;
    if (!current) return null;
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative?.deaths;
    return Object.fromEntries(this.deathCauses.map(({ key }) => [key, (current[key] ?? 0) - (previous?.[key] ?? 0)]));
  });
  // One « Records » table per group, flattened for the template — a table whose records all went unclaimed hides itself.
  protected readonly leaderTables = computed(() => LEADER_GROUPS.map(({ group, label, measures }) => ({ group, label, rows: this._leaderRows(group, measures) })));
  // Rows resolved here rather than in the template: every count sits under `snapshot`, except the hulls, which own a block so the chronicler can list them.
  protected readonly snapshotRows = computed<Omit<SnapshotRow, 'hideIfZero'>[]>(() => {
    const world = this.currentChapter()?.meta.world;
    if (!world) return [];
    const before = this._chronicler.previousChapter()?.meta.world;
    // `infected` is omitted at 0 (outbreak-style), so an absent count reads as 0 on either side.
    const rows: SnapshotRow[] = this.snapshotStats.map(({ hideIfZero, icon, key, label }) => {
      const value = world.snapshot[key] ?? 0;
      return { delta: before ? value - (before.snapshot[key] ?? 0) : undefined, hideIfZero, icon, key, label, value };
    });
    const boats = world.boats.total;
    rows.push({ delta: before ? boats - before.boats.total : undefined, hideIfZero: true, icon: undefined, key: 'boats', label: 'ui_boats', value: boats });
    return rows.filter(r => !r.hideIfZero || r.value > 0).map(({ delta, icon, key, label, value }) => ({ delta, icon, key, label, value }));
  });
  // Causes with > 0 deaths this chapter, sorted by count desc — 0-rows are hidden (16 categories incl. peste/poison/etc. that stay idle most chapters).
  protected readonly sortedDeathCauses = computed(() => {
    const counts = this.deathsSincePrevious();
    return counts ? this.deathCauses.filter(c => (counts[c.key] ?? 0) > 0).toSorted((a, b) => (counts[b.key] ?? 0) - (counts[a.key] ?? 0)) : [];
  });
  // Sum of per-cause death counts since previous chapter — `null` mirrors `deathsSincePrevious`.
  protected readonly totalDeathsSincePrevious = computed(() => {
    const breakdown = this.deathsSincePrevious();
    return breakdown ? Object.values(breakdown).reduce((sum, v) => sum + v, 0) : null;
  });

  // Only present entries, each tagged with `isNew` when the top entity changed since the previous chapter — or took a record that then had none.
  private _leaderRows(group: LeaderGroup, measures: LeaderMeasure[]): { data: LeaderRow; icon: string; label: string }[] {
    const current = this.currentChapter()?.meta.world.leaders?.[group];
    if (!current) return [];
    const previous = this._chronicler.previousChapter();
    return measures.flatMap((measure) => {
      const entry = current[measure];
      if (!entry) return [];
      const before = previous?.meta.world.leaders?.[group]?.[measure];
      const isNew = !!previous && (entry.id ?? entry.asset_id) !== (before?.id ?? before?.asset_id); // a species has no id, its `asset_id` standing in
      // Only a soul can reach here unnamed: every other entity row carries its name, and a species names itself through its `asset_id`.
      return [{ ...LEADER_MEASURES[measure], data: { ...entry, group, isNew, name: entry.name ?? (this._translate.instant('anonymous') as string) } }];
    });
  }

}

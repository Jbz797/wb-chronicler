import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { DeltaComponent } from '..';
import { DEATH_CAUSES, LEADER_GROUPS, LEADER_MEASURES } from '../../../../constants';
import { WorldHelpers } from '../../../../helpers';
import { LeaderGroup, LeaderMeasure, LeaderRow } from '../../../../interfaces';
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

  protected readonly deathCauses = DEATH_CAUSES;

  protected currentChapter = this._chronicler.currentChapter;

  // « Activité récente » rows, off the same reading the overview weighs to show the panel at all.
  protected readonly activityRows = computed(() => {
    const world = this.currentChapter()?.meta.world;
    return world ? WorldHelpers.activityRows(world, this._chronicler.previousChapter()?.meta.world) : [];
  });
  // Per-cause death delta vs the previous chapter — `null` on a world that never counted a death.
  protected readonly deathsSincePrevious = computed(() => {
    const world = this.currentChapter()?.meta.world;
    return world ? WorldHelpers.deathsSince(world, this._chronicler.previousChapter()?.meta.world) : null;
  });
  // One « Records » table per group, flattened for the template — a table whose records all went unclaimed hides itself.
  protected readonly leaderTables = computed(() => LEADER_GROUPS.map(({ group, label, measures }) => ({ group, label, rows: this._leaderRows(group, measures) })));
  // The world's counts, a zero left out unless it just fell there.
  protected readonly snapshotRows = computed(() => {
    const world = this.currentChapter()?.meta.world;
    return world ? WorldHelpers.snapshotRows(world, this._chronicler.previousChapter()?.meta.world) : [];
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

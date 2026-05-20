import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { CUMULATIVE_STATS, DEATH_CAUSES, SNAPSHOT_STATS } from '../../../../constants';
import { CompactPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services/chronicler.service';
import { DeltaComponent } from '../../../misc';

@Component({
  selector: 'app-world-stats',
  imports: [CompactPipe, DeltaComponent, NzDescriptionsModule],
  templateUrl: './world-stats.component.html',
})
export class WorldStatsComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  protected readonly cumulativeStats = CUMULATIVE_STATS;
  // Per-cumulative-stat delta vs previous chapter — at C1 the baseline is 0 so we get the cumulative count instead.
  protected readonly cumulativeDeltas = computed(() => {
    const current = this.currentChapter()?.meta.world.cumulative;
    if (!current) return null;
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative;
    return Object.fromEntries(this.cumulativeStats.map(({ key }) => [key, current[key] - (previous?.[key] ?? 0)]));
  });
  protected readonly deathCauses = DEATH_CAUSES;
  // Per-cause death count between previous chapter and current — at C1 the baseline is 0 so we get the cumulative count instead.
  protected readonly deathsSincePrevious = computed(() => {
    const current = this.currentChapter()?.meta.world.cumulative.deaths;
    if (!current) return null;
    const previous = this._chronicler.previousChapter()?.meta.world.cumulative.deaths;
    return Object.fromEntries(this.deathCauses.map(({ key }) => [key, current[key] - (previous?.[key] ?? 0)]));
  });
  protected readonly snapshotStats = SNAPSHOT_STATS;
  // Per-snapshot-stat delta vs previous chapter — `null` when no previous chapter to compare.
  protected readonly snapshotDeltas = computed(() => {
    const current = this.currentChapter()?.meta.world.snapshot;
    const previous = this._chronicler.previousChapter()?.meta.world.snapshot;
    if (!current || !previous) return null;
    return Object.fromEntries(this.snapshotStats.map(({ key }) => [key, current[key] - previous[key]]));
  });
  // Sum of per-cause death counts since previous chapter — `null` mirrors `deathsSincePrevious`.
  protected readonly totalDeathsSincePrevious = computed(() => {
    const breakdown = this.deathsSincePrevious();
    return breakdown ? Object.values(breakdown).reduce((sum, v) => sum + v, 0) : null;
  });

}

import { HttpClient } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { COMBAT_STATS, DEATH_CAUSES, HISTORY_DIR, SKILL_STATS, WORLD_STATS } from '../../../constants';
import { DeathCause, RarityCounts, World, WorldStat } from '../../../interfaces';
import { CompactPipe, TierPipe } from '../../../pipes';
import { ChroniclerService } from '../../../services/chronicler.service';
import { DeltaComponent, RankedStatComponent, RarityStatsComponent } from '../../misc';

@Component({
  selector: 'app-world-info',
  imports: [
    CompactPipe,
    DeltaComponent,
    NzCollapseModule,
    NzDescriptionsModule,
    NzDividerModule,
    NzEmptyModule,
    RankedStatComponent,
    RarityStatsComponent,
    TierPipe,
  ],
  templateUrl: './world-info.component.html',
  styleUrl: './world-info.component.scss',
})
export class WorldInfoComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  protected readonly combatStats = COMBAT_STATS;
  protected readonly deathCauses = DEATH_CAUSES;
  // Per-cause death count between previous chapter and current — at C1 the baseline is 0 so we get the cumulative count instead.
  protected readonly deathsSincePrevious = computed(() => {
    const current = this.currentChapter()?.meta.world.deaths_by_cause;
    if (!current) return null;
    const previous = this._chronicler.previousChapter()?.meta.world.deaths_by_cause;
    return Object.fromEntries(this.deathCauses.map(({ key }): [DeathCause, number] => [key, current[key] - (previous?.[key] ?? 0)])) as Record<DeathCause, number>;
  });
  // Per-bucket deltas vs the previous favorite. `null` when no comparable previous favorite — ranked stats handle their own deltas.
  protected readonly deltas = computed(() => {
    const current = this.currentChapter()?.meta.favorite;
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    if (!current || !previous) return null;

    const diffCounts = (a: RarityCounts, b: RarityCounts): RarityCounts => ({
      epic: a.epic - b.epic,
      legendary: a.legendary - b.legendary,
      normal: a.normal - b.normal,
      rare: a.rare - b.rare,
    });

    return {
      equipment: diffCounts(current.equipment, previous.equipment),
      traits: diffCounts(current.traits, previous.traits),
    };
  });
  protected readonly skillStats = SKILL_STATS;
  // Sum of per-cause death counts since previous chapter — `null` mirrors `deathsSincePrevious`.
  protected readonly totalDeathsSincePrevious = computed(() => {
    const breakdown = this.deathsSincePrevious();
    return breakdown ? Object.values(breakdown).reduce((sum, v) => sum + v, 0) : null;
  });
  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));
  protected readonly worldStats = WORLD_STATS;
  // Per-stat delta on `meta.world` — `null` when no previous chapter to compare.
  protected readonly worldDeltas = computed(() => {
    const current = this.currentChapter()?.meta.world;
    const previous = this._chronicler.previousChapter()?.meta.world;
    if (!current || !previous) return null;
    return Object.fromEntries(this.worldStats.map(({ key }): [WorldStat, number] => [key, current[key] - previous[key]])) as Record<WorldStat, number>;
  });

}

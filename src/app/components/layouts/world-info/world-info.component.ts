import { HttpClient } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';

import { HISTORY_DIR } from '../../../constants';
import { RarityCounts, World } from '../../../interfaces';
import { ChroniclerService } from '../../../services/chronicler.service';
import { DeltaComponent, RankedStatComponent, RarityStatsComponent } from '../../misc';

@Component({
  selector: 'app-world-info',
  imports: [DeltaComponent, NzDescriptionsModule, NzDividerModule, RankedStatComponent, RarityStatsComponent],
  templateUrl: './world-info.component.html',
  styleUrl: './world-info.component.scss',
})
export class WorldInfoComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Per-bucket deltas vs the previous favorite. `null` when no comparable previous favorite — HP/mana ranks compute their own deltas in `app-ranked-stat`.
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

    const diffStats = (a: typeof current.stats, b: typeof current.stats) => ({
      happiness: a.happiness - b.happiness,
      nutrition: a.nutrition - b.nutrition,
    });

    return {
      damage: (current.overview.damage_min + current.overview.damage_max) - (previous.overview.damage_min + previous.overview.damage_max),
      equipment: diffCounts(current.equipment, previous.equipment),
      stats: diffStats(current.stats, previous.stats),
      traits: diffCounts(current.traits, previous.traits),
    };
  });
  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));

}

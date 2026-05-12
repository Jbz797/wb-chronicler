import { HttpClient } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';

import { HISTORY_DIR } from '../../../constants';
import { RarityCounts, World } from '../../../interfaces';
import { ChroniclerService } from '../../../services/chronicler.service';
import { DeltaComponent, RarityStatsComponent } from '../../misc';

@Component({
  selector: 'app-world-info',
  imports: [DeltaComponent, NzDescriptionsModule, NzDividerModule, RarityStatsComponent],
  templateUrl: './world-info.component.html',
  styleUrl: './world-info.component.scss',
})
export class WorldInfoComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Per-bucket deltas (stats + equipment + traits) vs the previous chapter's favorite. `null` if there is no comparable previous favorite.
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
      health: a.health - b.health,
      mana: a.mana - b.mana,
      nutrition: a.nutrition - b.nutrition,
    });

    return {
      equipment: diffCounts(current.equipment, previous.equipment),
      stats: diffStats(current.stats, previous.stats),
      traits: diffCounts(current.traits, previous.traits),
    };
  });
  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));

}

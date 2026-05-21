import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { COMBAT_STATS, SKILL_STATS } from '../../../../constants';
import { RarityCounts } from '../../../../interfaces';
import { TierPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services/chronicler.service';
import { RankedStatComponent, RarityStatsComponent } from '../../../misc';

@Component({
  selector: 'app-favorite',
  imports: [NzDescriptionsModule, NzEmptyModule, RankedStatComponent, RarityStatsComponent, TierPipe],
  templateUrl: './favorite.component.html',
})
export class FavoriteComponent {

  protected readonly combatStats = COMBAT_STATS;
  protected readonly skillStats = SKILL_STATS;

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

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
  // Flatten the inventory dict into a list for the template — Python emits it already sorted alphabetically.
  protected readonly inventoryEntries = computed(() => {
    const inv = this.currentChapter()?.meta.favorite?.inventory ?? {};
    return Object.entries(inv).map(([key, amount]) => ({ amount, key }));
  });

}

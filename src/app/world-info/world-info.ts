import { HttpClient } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';

import { HISTORY_DIR } from '../constants';
import { RarityCounts, World } from '../interfaces';
import { ChroniclerService } from '../services/chronicler.service';

import { RarityStatsComponent } from './rarity-stats/rarity-stats';

@Component({
  selector: 'app-world-info',
  imports: [NzDescriptionsModule, NzDividerModule, RarityStatsComponent],
  templateUrl: './world-info.html',
  styleUrl: './world-info.scss',
})
export class WorldInfoComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Per-bucket deltas (equipment + traits) vs the previous chapter's favorite. `null` if there is no comparable previous favorite.
  protected readonly deltas = computed(() => {
    const current = this.currentChapter()?.meta.favorite;
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    if (!current || !previous) return null;
    const diff = (a: RarityCounts, b: RarityCounts): RarityCounts => ({
      epic: a.epic - b.epic,
      legendary: a.legendary - b.legendary,
      normal: a.normal - b.normal,
      rare: a.rare - b.rare,
    });
    return { equipment: diff(current.equipment, previous.equipment), traits: diff(current.traits, previous.traits) };
  });
  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));

}

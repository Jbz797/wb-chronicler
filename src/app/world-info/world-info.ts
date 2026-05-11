import { HttpClient } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { HISTORY_DIR } from '../constants';
import { World } from '../interfaces';
import { ChroniclerService } from '../services/chronicler.service';

@Component({
  selector: 'app-world-info',
  imports: [NzBadgeModule, NzDescriptionsModule, NzDividerModule, NzTagModule],
  templateUrl: './world-info.html',
  styleUrl: './world-info.scss',
})
export class WorldInfoComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Delta of each trait rarity count vs the previous chapter's favorite. `null` if there is no comparable previous favorite.
  protected readonly traitDeltas = computed(() => {
    const current = this.currentChapter()?.meta.favorite;
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    if (!current || !previous) return null;
    return {
      epic: current.traits.epic - previous.traits.epic,
      legendary: current.traits.legendary - previous.traits.legendary,
      normal: current.traits.normal - previous.traits.normal,
      rare: current.traits.rare - previous.traits.rare,
    };
  });
  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));

}

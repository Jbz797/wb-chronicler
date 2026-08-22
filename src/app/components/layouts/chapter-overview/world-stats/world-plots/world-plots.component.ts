import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { PLOT_TYPE_LABELS } from '../../../../../constants';
import { WorldPlot } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services';
import { PersonTagComponent } from '../../../../tags';

@Component({
  selector: 'app-world-plots',
  imports: [NzDescriptionsModule, NzTagModule, PersonTagComponent],
  templateUrl: './world-plots.component.html',
})
export class WorldPlotsComponent {

  private readonly _chronicler = inject(ChroniclerService);

  private readonly _signature = (plots: WorldPlot[]): string => plots.map(p => `${p.actor.id}:${p.type.id}`).toSorted((a, b) => a.localeCompare(b)).join('|');

  // Badged whenever the board has moved: one schemer scheming something else counts, and so does a plot hatched or abandoned since the previous chapter.
  protected readonly isNew = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.world.plots;
    if (!previous) return false;
    return this._signature(this._chronicler.currentChapter()?.meta.world.plots ?? []) !== this._signature(previous);
  });
  // Every scheme afoot, its label resolved here: WB hangs a plot on one schemer, and `actor/info.py <id> plot` tells the chronicler the rest.
  protected readonly rows = computed(() => {
    const plots = this._chronicler.currentChapter()?.meta.world.plots ?? [];
    return plots.map(({ actor, type }) => ({ icon: type.id, label: PLOT_TYPE_LABELS[type.id] ?? type.id, schemer: actor }));
  });

}

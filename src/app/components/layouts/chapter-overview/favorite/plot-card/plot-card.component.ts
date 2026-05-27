import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { PLOT_TYPE_LABELS } from '../../../../../constants';
import { ChroniclerService } from '../../../../../services/chronicler.service';

@Component({
  selector: 'app-plot-card',
  imports: [NzDescriptionsModule, NzProgressModule, NzTagModule],
  templateUrl: './plot-card.component.html',
})
export class PlotCardComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly plot = computed(() => this._chronicler.currentChapter()?.meta.favorite?.plot ?? null);
  // New if it appears (previous absent), or changes name/type.
  protected readonly isNew = computed(() => {
    const previousPlot = this._chronicler.previousChapter()?.meta.favorite?.plot;
    const current = this.plot();
    if (!current || previousPlot === undefined) return false;
    if (!previousPlot) return true;
    return previousPlot.type_id !== current.type_id || previousPlot.name !== current.name;
  });
  protected readonly progressColor = computed(() => (this.plot()?.progress ?? 0) >= 75 ? '#7a9b3a' : '#e6b94a');
  // Resolved target string — kingdom takes precedence, fallback to alliance, em-dash otherwise.
  protected readonly target = computed(() => {
    const p = this.plot();
    return p?.target_kingdom ?? p?.target_alliance ?? '—';
  });

  protected typeLabel = (id: string): string => PLOT_TYPE_LABELS[id] ?? id;

}

import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { PLOT_TYPE_LABELS } from '../../../../../constants';
import { ChroniclerService } from '../../../../../services';

@Component({
  selector: 'app-plot-card',
  imports: [NzDescriptionsModule, NzProgressModule, NzTagModule],
  templateUrl: './plot-card.component.html',
})
export class PlotCardComponent {

  public readonly isNew = input.required<boolean>();

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly plot = computed(() => this._chronicler.currentChapter()?.meta.favorite?.plot ?? null);
  protected readonly progressColor = computed(() => (this.plot()?.progress ?? 0) >= 75 ? '#7a9b3a' : '#e6b94a');
  // Resolved target string — kingdom takes precedence, fallback to alliance, em-dash otherwise.
  protected readonly target = computed(() => {
    const p = this.plot();
    return p?.target_kingdom ?? p?.target_alliance ?? '—';
  });

  protected typeLabel = (id: string): string => PLOT_TYPE_LABELS[id] ?? id;

}

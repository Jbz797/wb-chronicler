import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzProgressModule } from 'ng-zorro-antd/progress';

import { NewBadgeComponent } from '../..';
import { PLOT_TYPE_LABELS } from '../../../../../constants';
import { ChroniclerService } from '../../../../../services';
import { CityTagComponent, KingdomTagComponent } from '../../tags';

@Component({
  selector: 'app-plot-card',
  imports: [CityTagComponent, KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, NzProgressModule],
  templateUrl: './plot-card.component.html',
})
export class PlotCardComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly isNew = input.required<boolean>();

  protected readonly plot = computed(() => this._chronicler.currentChapter()?.meta.favorite?.plot ?? null);
  protected readonly progressColor = computed(() => (this.plot()?.progress ?? 0) >= 75 ? '#7a9b3a' : '#e6b94a');

  protected typeLabel = (id: string): string => PLOT_TYPE_LABELS[id] ?? id;

}

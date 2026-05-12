import { Component, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { RarityCounts } from '../../../interfaces';
import { DeltaComponent } from '../delta/delta.component';

@Component({
  selector: 'app-rarity-stats',
  imports: [DeltaComponent, NzDescriptionsModule],
  templateUrl: './rarity-stats.component.html',
  styleUrl: './rarity-stats.component.scss',
})
export class RarityStatsComponent {

  public readonly counts = input.required<RarityCounts>();
  public readonly deltas = input<RarityCounts | null>(null);
  public readonly title = input.required<string>();

}

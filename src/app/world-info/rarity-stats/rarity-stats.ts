import { Component, input } from '@angular/core';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { RarityCounts } from '../../interfaces';

@Component({
  selector: 'app-rarity-stats',
  imports: [NzBadgeModule, NzDescriptionsModule, NzTagModule],
  templateUrl: './rarity-stats.html',
})
export class RarityStatsComponent {

  public readonly counts = input.required<RarityCounts>();
  public readonly deltas = input<RarityCounts | null>(null);
  public readonly title = input.required<string>();

}

import { Component, computed, input } from '@angular/core';

import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { RELATION_STATUS_LABELS, RELATION_STATUS_NZ_COLORS } from '../../../../../constants';
import { KingdomRelation } from '../../../../../interfaces';
import { KingdomTagComponent } from '../../../../tags';

@Component({
  selector: 'app-kingdom-relations',
  imports: [KingdomTagComponent, NzTableModule, NzTagModule],
  templateUrl: './kingdom-relations.component.html',
})
export class KingdomRelationsComponent {

  protected readonly statusColor = RELATION_STATUS_NZ_COLORS;
  protected readonly statusLabel = RELATION_STATUS_LABELS;

  public readonly relations = input.required<KingdomRelation[]>();

  protected readonly sorted = computed(() => this.relations().toSorted((a, b) => b.opinion.total - a.opinion.total));

  // 4-tier coloring: ≥+50 = `.tier-full` (vert), ≥0 = `.tier-high` (or), ≥-50 = `.tier-mid` (info), < -50 = `.tier-low` (rouge).
  protected opinionClass = (total: number): string => {
    if (total >= 50) return 'tier-full';
    if (total >= 0) return 'tier-high';
    if (total >= -50) return 'tier-mid';
    return 'tier-low';
  };

}

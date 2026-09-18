import { Component, computed, inject, input } from '@angular/core';

import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { TranslatePipe } from '@ngx-translate/core';

import { RELATION_STATUS_NZ_COLORS } from '../../../../../constants';
import { KingdomRelation } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services';
import { KingdomTagComponent } from '../../tags';

@Component({
  selector: 'app-kingdom-relations',
  imports: [KingdomTagComponent, NzTableModule, NzTagModule, TranslatePipe],
  templateUrl: './kingdom-relations.component.html',
  styleUrl: './kingdom-relations.component.scss',
})
export class KingdomRelationsComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly statusColor = RELATION_STATUS_NZ_COLORS;

  public readonly relations = input.required<KingdomRelation[]>();

  protected readonly sorted = computed(() => this.relations().toSorted((a, b) => b.opinion.total - a.opinion.total));

  // Each crown's opinion a chapter before, by id — none when the favourite's kingdom changed, two strangers having no standing to compare.
  private readonly _before = computed(() => {
    const previous = this._chronicler.carriesOver('kingdom') ? this._chronicler.previousChapter()?.meta.kingdom?.relations : undefined;
    return new Map((previous ?? []).map(r => [r.kingdom.id, r.opinion.total]));
  });

  // 4-tier coloring: ≥+50 = `.tier-full` (vert), ≥0 = `.tier-high` (or), ≥-50 = `.tier-mid` (info), < -50 = `.tier-low` (rouge).
  protected opinionClass = (total: number): string => {
    if (total >= 50) return 'tier-full';
    if (total >= 0) return 'tier-high';
    return total >= -50 ? 'tier-mid' : 'tier-low';
  };

  // Up or down since the chapter before, `null` for an opinion unchanged or a crown newly met — an arrow alone, the cell already printing the value.
  protected trend = (relation: KingdomRelation): 'down' | 'up' | null => {
    const before = this._before().get(relation.kingdom.id);
    if (before === undefined || before === relation.opinion.total) return null;
    return relation.opinion.total > before ? 'up' : 'down';
  };

}

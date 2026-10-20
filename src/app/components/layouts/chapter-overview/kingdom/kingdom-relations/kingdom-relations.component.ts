import { Component, computed, inject, input } from '@angular/core';

import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { TranslatePipe } from '@ngx-translate/core';

import { RELATION_STATUS_NZ_COLORS } from '../../../../../constants';
import { KingdomRelation } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services';
import { NewBadgeComponent } from '../../new-badge/new-badge.component';
import { KingdomTagComponent } from '../../tags';

@Component({
  selector: 'app-kingdom-relations',
  imports: [KingdomTagComponent, NewBadgeComponent, NzTableModule, NzTagModule, TranslatePipe],
  templateUrl: './kingdom-relations.component.html',
  styleUrl: './kingdom-relations.component.scss',
})
export class KingdomRelationsComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly statusColor = RELATION_STATUS_NZ_COLORS;

  public readonly relations = input.required<KingdomRelation[]>();

  protected standing = (relation: KingdomRelation): number => relation.opinion.total + (relation.their_opinion ?? 0);

  protected readonly sorted = computed(() => this.relations().toSorted((a, b) => this.standing(b) - this.standing(a)));

  // Each crown's opinion a chapter before, by id — `null` when the favourite's kingdom changed, two strangers having no standing to compare.
  private readonly _before = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.kingdom?.relations ?? [];
    return this._chronicler.carriesOver('kingdom') ? new Map(previous.map(r => [r.kingdom.id, this.standing(r)])) : null;
  });

  protected isNew = (relation: KingdomRelation): boolean => this._before()?.has(relation.kingdom.id) === false;

  // 4-tier coloring: ≥+50 = `.tier-full` (vert), ≥0 = `.tier-high` (or), ≥-50 = `.tier-mid` (info), < -50 = `.tier-low` (rouge).
  protected opinionClass = (total: number): string => {
    if (total >= 50) return 'tier-full';
    if (total >= 0) return 'tier-high';
    return total >= -50 ? 'tier-mid' : 'tier-low';
  };

  // Up or down since the chapter before, `null` for an opinion unchanged or a crown newly met — an arrow alone, the cell already printing the value.
  protected trend = (relation: KingdomRelation): 'down' | 'up' | null => {
    const before = this._before()?.get(relation.kingdom.id);
    if (before === undefined || before === this.standing(relation)) return null;
    return this.standing(relation) > before ? 'up' : 'down';
  };

}

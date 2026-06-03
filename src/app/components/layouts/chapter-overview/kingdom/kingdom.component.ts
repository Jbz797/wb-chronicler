import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { RELATION_STATUS_LABELS, RELATION_STATUS_NZ_COLORS } from '../../../../constants';
import { KingdomRelation, KingdomWar } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { RankedStatComponent } from '../../../misc';
import { KingdomTagComponent } from '../../../tags';

import { WarCardComponent } from './war-card/war-card.component';

@Component({
  selector: 'app-kingdom',
  imports: [KingdomTagComponent, NzDescriptionsModule, NzTableModule, NzTagModule, RankedStatComponent, WarCardComponent],
  templateUrl: './kingdom.component.html',
})
export class KingdomComponent {

  protected readonly statusColor = RELATION_STATUS_NZ_COLORS;
  protected readonly statusLabel = RELATION_STATUS_LABELS;

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly kingdom = computed(() => this._chronicler.currentChapter()?.meta.kingdom ?? null);
  // Relations sorted by status (enemies first, then allies, neutrals last), then by age desc within status.
  protected readonly sortedRelations = computed<KingdomRelation[]>(() => {
    const weight: Record<KingdomRelation['status'], number> = { ally: 1, enemy: 0, neutral: 2 };
    const relations = this.kingdom()?.relations ?? [];
    return relations.toSorted((a, b) => weight[a.status] - weight[b.status] || b.age_years - a.age_years);
  });
  // Set of war ids that surfaced this chapter (not present in the previous chapter's wars list).
  protected readonly startedWarIds = computed(() => {
    const wars: KingdomWar[] = this.kingdom()?.wars ?? [];
    const previousWars: KingdomWar[] = this._chronicler.previousChapter()?.meta.kingdom?.wars ?? [];
    const previousIds = new Set<number>(previousWars.map(w => w.id));
    return new Set<number>(wars.filter(w => !previousIds.has(w.id)).map(w => w.id));
  });

}

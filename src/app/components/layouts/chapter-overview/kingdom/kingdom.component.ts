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
  // Relations sorted by opinion total (favourable first, hostile last).
  protected readonly sortedRelations = computed<KingdomRelation[]>(() => {
    const relations = this.kingdom()?.relations ?? [];
    return relations.toSorted((a, b) => b.opinion.total - a.opinion.total);
  });
  // Set of war ids that surfaced this chapter (not present in the previous chapter's wars list).
  protected readonly startedWarIds = computed(() => {
    const wars: KingdomWar[] = this.kingdom()?.wars ?? [];
    const previousWars: KingdomWar[] = this._chronicler.previousChapter()?.meta.kingdom?.wars ?? [];
    const previousIds = new Set<number>(previousWars.map(w => w.id));
    return new Set<number>(wars.filter(w => !previousIds.has(w.id)).map(w => w.id));
  });

  // 4-tier coloring: ≥+50 = `.tier-full` (vert), ≥0 = `.tier-high` (or), ≥-50 = `.tier-mid` (info), < -50 = `.tier-low` (rouge).
  protected opinionClass = (total: number): string => {
    if (total >= 50) return 'tier-full';
    if (total >= 0) return 'tier-high';
    if (total >= -50) return 'tier-mid';
    return 'tier-low';
  };

}

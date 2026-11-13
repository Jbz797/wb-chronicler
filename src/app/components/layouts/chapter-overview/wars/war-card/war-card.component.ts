import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { SectionRowDirective } from '../../../../../directives';
import { War, WarSideKey } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services';
import { DeltaComponent } from '../../delta/delta.component';
import { NewBadgeComponent } from '../../new-badge/new-badge.component';
import { KingdomTagComponent } from '../../tags';

@Component({
  selector: 'app-war-card',
  imports: [DeltaComponent, KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, NzTagModule, SectionRowDirective, TranslatePipe],
  templateUrl: './war-card.component.html',
})
export class WarCardComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _translate = inject(TranslateService);

  public readonly war = input.required<War>();

  // Per-stat delta on both camps and the stake against the same war a chapter ago — `null` where no chapter precedes, or where this war was not declared yet.
  protected readonly deltas = computed(() => {
    const w = this.war();
    const before = this._chronicler.previousChapter()?.meta.wars?.find(x => x.metadata.id === w.metadata.id);
    if (!before) return null;
    const diff = (side: WarSideKey) => ({
      cities: w[side].cities - before[side].cities,
      deaths: w[side].deaths - before[side].deaths,
      nobles: (w[side].nobles ?? 0) - (before[side].nobles ?? 0),
      pop: w[side].pop - before[side].pop,
      taken: (w[side].taken ?? 0) - (before[side].taken ?? 0),
      warriors: w[side].warriors - before[side].warriors,
    });
    return { attackers: diff('attackers'), defenders: diff('defenders'), stake: w.metadata.renown_at_stake - before.metadata.renown_at_stake };
  });
  // A war the chapter before had not declared — its card opens with the same badge a new panel wears.
  protected readonly isNew = computed(() => {
    const previous = this._chronicler.previousChapter();
    return !!previous && (previous.meta.wars ?? []).every(x => x.metadata.id !== this.war().metadata.id);
  });

  // The declaring crown, said apart only once the attacking camp is no longer it alone: it left the war, fell, or fights among allies.
  protected isDeclarerAlone = (war: War): boolean => war.attackers.kingdoms.length === 1 && war.attackers.kingdoms[0]?.id === war.metadata.started_by_kingdom.id;

  // `.tier-full` on the side ahead, `.tier-low` on the one behind, nothing where they tie. `isInverted` for the counts a side would rather keep low.
  protected sideClass = (attackers: number, defenders: number, side: WarSideKey, isInverted = false): string => {
    const own = side === 'attackers' ? attackers : defenders;
    const other = side === 'attackers' ? defenders : attackers;
    if (own === other) return '';
    return (isInverted ? own < other : own > other) ? 'tier-full' : 'tier-low';
  };

  // Caller gates this behind `@if (w.metadata.war_type)` — WB leaves the kind unset on most declarations.
  protected typeLabel = (war: War): string => this._translate.instant(`war_type_${war.metadata.war_type}`) as string;

}

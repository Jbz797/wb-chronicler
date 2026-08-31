import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { WAR_TYPE_LABELS } from '../../../../../constants';
import { SectionRowDirective } from '../../../../../directives';
import { War, WarSideKey } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services';
import { DeltaComponent } from '../../delta/delta.component';
import { NewBadgeComponent } from '../../new-badge/new-badge.component';
import { KingdomTagComponent } from '../../tags';

@Component({
  selector: 'app-war-card',
  imports: [DeltaComponent, KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, NzTagModule, SectionRowDirective],
  templateUrl: './war-card.component.html',
})
export class WarCardComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly war = input.required<War>();

  // Per-stat delta on both camps against the same war a chapter ago — `null` where no chapter precedes, or where this war had not been declared yet.
  protected readonly deltas = computed(() => {
    const w = this.war();
    const before = this._chronicler.previousChapter()?.meta.wars.find(x => x.metadata.id === w.metadata.id);
    if (!before) return null;
    const diff = (side: WarSideKey) => ({
      cities: w[side].cities - before[side].cities,
      deaths: w[side].deaths - before[side].deaths,
      population: w[side].population - before[side].population,
      warriors: w[side].warriors - before[side].warriors,
    });
    return { attackers: diff('attackers'), defenders: diff('defenders') };
  });
  // A war the chapter before had not declared — its card opens with the same badge a new panel wears.
  protected readonly isNew = computed(() => {
    const previous = this._chronicler.previousChapter();
    return !!previous && previous.meta.wars.every(x => x.metadata.id !== this.war().metadata.id);
  });

  // `.tier-full` on the side ahead, `.tier-low` on the one behind, nothing where they tie. `isInverted` for the counts a side would rather keep low.
  protected sideClass = (attackers: number, defenders: number, side: WarSideKey, isInverted = false): string => {
    const own = side === 'attackers' ? attackers : defenders;
    const other = side === 'attackers' ? defenders : attackers;
    if (own === other) return '';
    return (isInverted ? own < other : own > other) ? 'tier-full' : 'tier-low';
  };

  // Caller gates this behind `@if (w.metadata.war_type)` — WB leaves the kind unset on most declarations.
  protected typeLabel = (war: War): string => WAR_TYPE_LABELS[war.metadata.war_type!];

}

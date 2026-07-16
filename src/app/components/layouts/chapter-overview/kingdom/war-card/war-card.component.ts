import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { WAR_TYPE_LABELS } from '../../../../../constants';
import { SectionRowDirective } from '../../../../../directives';
import { KingdomWar } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services';
import { DeltaComponent, NewBadgeComponent } from '../../../../misc';
import { KingdomTagComponent } from '../../../../tags';

@Component({
  selector: 'app-war-card',
  imports: [DeltaComponent, KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, NzTagModule, SectionRowDirective],
  templateUrl: './war-card.component.html',
})
export class WarCardComponent {

  protected readonly chronicler = inject(ChroniclerService);

  public readonly isNew = input.required<boolean>();
  public readonly war = input.required<KingdomWar>();

  // Per-stat delta (both sides) vs the same war in the previous chapter — `null` when no previous chapter or war absent.
  protected readonly deltas = computed(() => {
    const w = this.war();
    const previous = this.chronicler.previousChapter()?.meta.kingdom?.wars?.find(x => x.id === w.id);
    if (!previous) return null;
    const diff = (side: 'attackers' | 'defenders') => ({
      cities: w.cities[side] - previous.cities[side],
      deaths: w.deaths[side] - previous.deaths[side],
      populations: w.populations[side] - previous.populations[side],
      warriors: w.warriors[side] - previous.warriors[side],
    });
    return { attackers: diff('attackers'), defenders: diff('defenders') };
  });

  protected ourAlliance = (war: KingdomWar): KingdomWar['attacker_alliance'] => war[`${war.side}_alliance`];

  protected ourSectionTitle = (war: KingdomWar): string => `Notre camp (${war.side === 'attacker' ? 'atk' : 'def'})`;

  // Field key on the war's `populations`/`warriors`/`deaths` for the kingdom's own side.
  protected ourSide = (war: KingdomWar): 'attackers' | 'defenders' => `${war.side}s`;

  // `.tier-full` (vert) on the winning side, `.tier-low` (rouge) on the losing side; empty when equal. `isInverted=true` when lower is better (e.g. deaths).
  protected sideClass = (stat: { attackers: number; defenders: number }, side: 'attackers' | 'defenders', isInverted = false): string => {
    const own = stat[side];
    const other = stat[side === 'attackers' ? 'defenders' : 'attackers'];
    if (own === other) return '';
    const hasWon = isInverted ? own < other : own > other;
    return hasWon ? 'tier-full' : 'tier-low';
  };

  protected theirAlliance = (war: KingdomWar): KingdomWar['attacker_alliance'] => war[war.side === 'attacker' ? 'defender_alliance' : 'attacker_alliance'];

  protected theirSectionTitle = (war: KingdomWar): string => `Adversaires (${war.side === 'attacker' ? 'def' : 'atk'})`;

  // Field key on the war's `populations`/`warriors`/`deaths` for the opposing side.
  protected theirSide = (war: KingdomWar): 'attackers' | 'defenders' => war.side === 'attacker' ? 'defenders' : 'attackers';

  // Caller (`war-card.component.html`) gates the call behind `@if (w.war_type)`.
  protected typeLabel = (war: KingdomWar): string => WAR_TYPE_LABELS[war.war_type!];

}

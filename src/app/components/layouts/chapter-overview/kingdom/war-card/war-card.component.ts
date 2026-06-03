import { Component, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { SectionRowDirective } from '../../../../../directives';
import { KingdomWar } from '../../../../../interfaces';
import { NewBadgeComponent } from '../../../../misc';
import { KingdomTagComponent } from '../../../../tags';

@Component({
  selector: 'app-war-card',
  imports: [KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, NzTagModule, SectionRowDirective],
  templateUrl: './war-card.component.html',
})
export class WarCardComponent {

  public readonly isNew = input.required<boolean>();
  public readonly war = input.required<KingdomWar>();

  protected ourAlliance = (war: KingdomWar): { id: number; name: string } | null => war.side === 'attacker' ? war.attacker_alliance : war.defender_alliance;

  protected ourSectionTitle = (war: KingdomWar): string => `Notre camp (${war.side === 'attacker' ? 'atk' : 'def'})`;

  // Field key on the war's `populations`/`warriors`/`deaths` for the kingdom's own side.
  protected ourSide = (war: KingdomWar): 'attackers' | 'defenders' => war.side === 'attacker' ? 'attackers' : 'defenders';

  // `.tier-full` (vert) on the winning side, `.tier-low` (rouge) on the losing side; empty when equal. `inverted=true` when lower is better (e.g. deaths).
  protected sideClass = (stat: { attackers: number; defenders: number }, side: 'attackers' | 'defenders', inverted = false): string => {
    const own = stat[side];
    const other = side === 'attackers' ? stat.defenders : stat.attackers;
    if (own === other) return '';
    const wins = inverted ? own < other : own > other;
    return wins ? 'tier-full' : 'tier-low';
  };

  protected theirAlliance = (war: KingdomWar): { id: number; name: string } | null => war.side === 'attacker' ? war.defender_alliance : war.attacker_alliance;

  protected theirSectionTitle = (war: KingdomWar): string => `Adversaires (${war.side === 'attacker' ? 'def' : 'atk'})`;

  // Field key on the war's `populations`/`warriors`/`deaths` for the opposing side.
  protected theirSide = (war: KingdomWar): 'attackers' | 'defenders' => war.side === 'attacker' ? 'defenders' : 'attackers';

}

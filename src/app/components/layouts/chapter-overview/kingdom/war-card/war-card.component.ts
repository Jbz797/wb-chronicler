import { Component, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { KingdomWar } from '../../../../../interfaces';
import { NewBadgeComponent } from '../../../../misc';
import { KingdomTagComponent } from '../../../../tags';

@Component({
  selector: 'app-war-card',
  imports: [KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, NzTagModule],
  templateUrl: './war-card.component.html',
})
export class WarCardComponent {

  public readonly isNew = input.required<boolean>();
  public readonly war = input.required<KingdomWar>();

  // Flattens the (up to two) alliances of a war into one list — lets the template iterate once instead of branching on each side.
  protected coalitions = (war: KingdomWar): { name: string; side: 'atk' | 'def' }[] => [
    ...war.attacker_alliance ? [{ name: war.attacker_alliance.name, side: 'atk' as const }] : [],
    ...war.defender_alliance ? [{ name: war.defender_alliance.name, side: 'def' as const }] : [],
  ];

  protected sideLabel = (war: KingdomWar): string => war.side === 'attacker' ? 'Attaquants' : 'Défenseurs';

}

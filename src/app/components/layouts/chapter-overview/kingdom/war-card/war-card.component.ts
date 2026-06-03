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

  protected sideLabel = (war: KingdomWar): string => war.side === 'attacker' ? 'Attaquants' : 'Défenseurs';

}

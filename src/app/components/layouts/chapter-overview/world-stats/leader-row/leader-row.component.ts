import { Component, input } from '@angular/core';

import { LeaderRow } from '../../../../../interfaces';
import { NewBadgeComponent } from '../../../../misc';
import { CityTagComponent, KingdomTagComponent, PersonTagComponent } from '../../../../tags';

@Component({
  selector: 'app-leader-row',
  imports: [CityTagComponent, KingdomTagComponent, NewBadgeComponent, PersonTagComponent],
  templateUrl: './leader-row.component.html',
})
export class LeaderRowComponent {

  public readonly row = input.required<LeaderRow>();

}

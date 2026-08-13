import { Component, input } from '@angular/core';

import { LeaderRow } from '../../../../../interfaces';
import { SpeciesNamePipe } from '../../../../../pipes';
import { NewBadgeComponent } from '../../../../misc';
import { CityTagComponent, ClanTagComponent, FamilyTagComponent, KingdomTagComponent, PersonTagComponent, SubspeciesTagComponent } from '../../../../tags';

@Component({
  selector: 'app-leader-row',
  imports: [
    CityTagComponent, ClanTagComponent, FamilyTagComponent, KingdomTagComponent, NewBadgeComponent, PersonTagComponent, SpeciesNamePipe, SubspeciesTagComponent,
  ],
  templateUrl: './leader-row.component.html',
})
export class LeaderRowComponent {

  public readonly row = input.required<LeaderRow>();

}

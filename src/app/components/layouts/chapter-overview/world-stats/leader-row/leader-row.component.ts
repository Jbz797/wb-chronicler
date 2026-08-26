import { Component, input } from '@angular/core';

import { LeaderRow } from '../../../../../interfaces';
import { SpeciesNamePipe } from '../../../../../pipes';
import {
  CityTagComponent, ClanTagComponent, CultureTagComponent, FamilyTagComponent, KingdomTagComponent, LanguageTagComponent, PersonTagComponent,
  ReligionTagComponent, SubspeciesTagComponent,
} from '../../tags';

@Component({
  selector: 'app-leader-row',
  imports: [
    CityTagComponent,
    ClanTagComponent,
    CultureTagComponent,
    FamilyTagComponent,
    KingdomTagComponent,
    LanguageTagComponent,
    PersonTagComponent,
    ReligionTagComponent,
    SpeciesNamePipe,
    SubspeciesTagComponent,
  ],
  templateUrl: './leader-row.component.html',
  styleUrl: './leader-row.component.scss',
})
export class LeaderRowComponent {

  public readonly row = input.required<LeaderRow>();

}

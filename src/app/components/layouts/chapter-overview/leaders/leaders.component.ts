import { Component, computed, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { LEADER_FAMILY_ROWS, LEADER_PERSON_ROWS } from '../../../../constants';
import { Leaders } from '../../../../interfaces';
import { FamilyTagComponent, PersonTagComponent } from '../../../tags';

@Component({
  selector: 'app-leaders',
  imports: [FamilyTagComponent, NzDescriptionsModule, PersonTagComponent],
  templateUrl: './leaders.component.html',
})
export class LeadersComponent {

  public readonly leaders = input<Leaders | undefined>();

  // The one family the panel names; the four other rankings stay in the JSON, for the chronicler.
  protected readonly familyRows = computed(() => {
    const families = this.leaders()?.families;
    return LEADER_FAMILY_ROWS.flatMap((row) => {
      const reference = families?.[row.key];
      return reference ? [{ ...row, ref: reference }] : [];
    });
  });
  // The five souls the panel names, in the order they read best: fame, power, violence, fortune, age.
  protected readonly personRows = computed(() => {
    const persons = this.leaders()?.persons;
    return LEADER_PERSON_ROWS.flatMap((row) => {
      const reference = persons?.[row.key];
      return reference ? [{ ...row, ref: reference }] : [];
    });
  });

}

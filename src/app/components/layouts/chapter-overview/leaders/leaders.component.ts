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

  public readonly leaders = input.required<Leaders | undefined>();

  // The one family the panel names — `new.py` folds the four others out of the chapter, `<tier>/info.py <id> leaders` still ranking them all.
  protected readonly familyRows = computed(() => {
    const families = this.leaders()?.families;
    return LEADER_FAMILY_ROWS.flatMap((row) => {
      const reference = families?.[row.key];
      return reference ? [{ ...row, ref: reference }] : [];
    });
  });
  // The souls the panel names, in the order they read best: fame, power, violence, fortune, age. The eight other podiums are folded out of the chapter.
  protected readonly personRows = computed(() => {
    const persons = this.leaders()?.persons;
    return LEADER_PERSON_ROWS.flatMap((row) => {
      const reference = persons?.[row.key];
      return reference ? [{ ...row, ref: reference }] : [];
    });
  });

}

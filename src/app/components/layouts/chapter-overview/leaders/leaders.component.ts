import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe } from '@ngx-translate/core';

import { LEADER_CLAN_ROWS, LEADER_PERSON_ROWS } from '../../../../constants';
import { PopulatedTier } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { NewBadgeComponent } from '../new-badge/new-badge.component';
import { ClanTagComponent, PersonTagComponent } from '../tags';

@Component({
  selector: 'app-leaders',
  imports: [ClanTagComponent, NewBadgeComponent, NzDescriptionsModule, PersonTagComponent, TranslatePipe],
  templateUrl: './leaders.component.html',
})
export class LeadersComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<PopulatedTier>();

  private readonly _before = computed(() => this._chronicler.previousChapter()?.meta[this.source()]?.leaders);
  // New on a change of holder, or on a record taken that had none — as the world's « Palmarès » counts it, but only for the body the chapter before named.
  private readonly _carries = computed(() => this._chronicler.carriesOver(this.source()));
  private readonly _leaders = computed(() => this._chronicler.currentChapter()?.meta[this.source()]?.leaders);
  // The one clan the panel names — `new.py` folds the two others and the families out of the chapter, `<tier>/info.py <id> leaders` still ranking them all.
  protected readonly clanRows = computed(() => {
    const clans = this._leaders()?.clans;
    const before = this._before()?.clans;
    return LEADER_CLAN_ROWS.flatMap((row) => {
      const reference = clans?.[row.key];
      return reference ? [{ ...row, isNew: this._carries() && reference.id !== before?.[row.key]?.id, ref: reference }] : [];
    });
  });
  // The souls the panel names, in the order they read best: fame, power, violence, fortune, age. The eight other podiums are folded out of the chapter.
  protected readonly personRows = computed(() => {
    const persons = this._leaders()?.persons;
    const before = this._before()?.persons;
    return LEADER_PERSON_ROWS.flatMap((row) => {
      const reference = persons?.[row.key];
      return reference ? [{ ...row, isNew: this._carries() && reference.id !== before?.[row.key]?.id, ref: reference }] : [];
    });
  });

}

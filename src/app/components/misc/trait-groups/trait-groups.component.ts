import { Component, computed, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TRAIT_GROUP_LABELS } from '../../../constants';
import { TraitGroup, TraitGroupCounts } from '../../../interfaces';
import { DeltaComponent } from '../delta/delta.component';

@Component({
  selector: 'app-trait-groups',
  imports: [DeltaComponent, NzDescriptionsModule],
  templateUrl: './trait-groups.component.html',
  styleUrl: './trait-groups.component.scss',
})
export class TraitGroupsComponent {

  public readonly counts = input.required<TraitGroupCounts>();
  public readonly deltas = input.required<TraitGroupCounts | null>();
  public readonly title = input.required<string>();

  // Worn groups only, alphabetical — WB gives clans seven and a clan swears a handful, so the five it never touched would be five empty boxes.
  protected readonly rows = computed(() => {
    const counts = this.counts();
    const groups = Object.keys(counts).toSorted((a, b) => a.localeCompare(b)) as TraitGroup[];
    return groups.map(group => ({ delta: this.deltas()?.[group], group, label: TRAIT_GROUP_LABELS[group], value: counts[group] ?? 0 }));
  });

}

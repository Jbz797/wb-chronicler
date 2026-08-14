import { Component, computed, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TRAIT_GROUP_LABELS } from '../../../constants';
import { TraitGroup, TraitGroupCounts } from '../../../interfaces';

@Component({
  selector: 'app-trait-groups',
  imports: [NzDescriptionsModule],
  templateUrl: './trait-groups.component.html',
  styleUrl: './trait-groups.component.scss',
})
export class TraitGroupsComponent {

  public readonly counts = input.required<TraitGroupCounts>();
  public readonly title = input.required<string>();

  // Worn groups only, merged on their label so the two reproduction ids read as one row, sorted on it: `advanced_brain` files under C for « Cerveau amélioré ».
  protected readonly rows = computed(() => {
    const counts = this.counts();
    const merged = new Map<string, { group: TraitGroup; label: string; value: number }>();
    for (const group of Object.keys(counts) as TraitGroup[]) {
      const label = TRAIT_GROUP_LABELS[group];
      const row = merged.get(label) ?? { group, label, value: 0 };
      merged.set(label, { ...row, value: row.value + (counts[group] ?? 0) });
    }
    return merged.values().toArray().toSorted((a, b) => a.label.localeCompare(b.label, 'fr'));
  });

}

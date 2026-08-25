import { Component, computed, inject, input } from '@angular/core';

import { TraitSummarySource } from '../../../interfaces';
import { ChroniclerService } from '../../../services';
import { NewBadgeComponent } from '../new-badge/new-badge.component';

@Component({
  selector: 'app-trait-summary',
  imports: [NewBadgeComponent],
  templateUrl: './trait-summary.component.html',
  styleUrl: './trait-summary.component.scss',
})
export class TraitSummaryComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly source = input.required<TraitSummarySource>();
  public readonly title = input.required<string>();

  // Absent only where the block itself is — a favorite with no clan has no clan panel either. Where the entity stands, its summary is written.
  protected readonly summary = computed(() => this._chronicler.currentChapter()?.meta[this.source()]?.traits);
  // Badged only against a summary that existed and read otherwise — a first one, on an entity the chronicle had never met, is not a change.
  protected readonly isNew = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta[this.source()]?.traits;
    return !!previous && previous !== this.summary();
  });

}

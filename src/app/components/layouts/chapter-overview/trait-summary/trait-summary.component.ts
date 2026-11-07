import { Component, computed, inject, input } from '@angular/core';

import { TraitSummarySource } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { NewBadgeComponent } from '../new-badge/new-badge.component';

@Component({
  selector: 'app-trait-summary',
  imports: [NewBadgeComponent],
  templateUrl: './trait-summary.component.html',
  styleUrl: './trait-summary.component.scss',
})
export class TraitSummaryComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly heading = input.required<string>(); // not `title`: a static attribute of that name lands in the DOM too, raising a native tooltip
  public readonly source = input.required<TraitSummarySource>();

  // Absent only where the block itself is — a favorite with no clan has no clan panel either. Where the entity stands, its summary is written.
  protected readonly summary = computed(() => this._chronicler.currentChapter()?.meta[this.source()]?.traits);

  private readonly _unbracketed = (text: string): string => text.replaceAll(this._freshMark, '$1');

  // Badged only against a summary that existed and read otherwise — a first one, on an entity the chronicle had never met, is not a change.
  protected readonly isNew = computed(() => {
    if (!this._chronicler.carriesOver(this.source())) return false; // another body's summary is no rewriting of this one's
    const previous = this._chronicler.previousChapter()?.meta[this.source()]?.traits;
    return !!previous && this._unbracketed(previous) !== this._unbracketed(this.summary() ?? ''); // carried on, a summary loses its brackets and nothing else
  });

  private readonly _freshMark = /\[([^\]]*)\]/g; // what a rewritten summary tells new, bracketed by the chronicler (`new.py`'s `_FRESH`)

  // The summary in runs, its brackets gone: split on them, every odd run is what it tells new.
  protected readonly runs = computed(() => {
    const runs = (this.summary() ?? '').split(this._freshMark).map((text, index) => ({ fresh: index % 2 === 1, text }));
    return runs.filter(run => run.text);
  });

}

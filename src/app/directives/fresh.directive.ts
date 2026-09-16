import { Directive, effect, inject, input, TemplateRef, ViewContainerRef } from '@angular/core';

// Builds the host anew on each new value: `nz-descriptions` keys a row's content to its place, and one raised on a neighbour's outlet projects nothing — blank cells
@Directive({ selector: '[appFresh]' })
export class FreshDirective {

  private readonly _template = inject(TemplateRef<unknown>);
  private readonly _view = inject(ViewContainerRef);

  public readonly appFresh = input.required<unknown>();

  constructor() {
    effect(() => {
      this.appFresh(); // read for the dependency alone: the value never reaches the view, only the news that another one has come
      this._view.clear();
      this._view.createEmbeddedView(this._template);
    });
  }

}

import { Directive, effect, inject, input, TemplateRef, ViewContainerRef } from '@angular/core';

// Renders the host where the count has something to tell — absent and 0 alike stay silent, where `*appPresent` keeps a nought. Structural, so no `@if` is spent.
@Directive({ selector: '[appNonZero]' })
export class NonZeroDirective {

  private readonly _template = inject(TemplateRef<unknown>);
  private readonly _view = inject(ViewContainerRef);

  public readonly appNonZero = input.required<number | undefined>();

  constructor() {
    effect(() => {
      this._view.clear();
      if (this.appNonZero()) this._view.createEmbeddedView(this._template);
    });
  }

}

import { Directive, effect, inject, input, TemplateRef, ViewContainerRef } from '@angular/core';

// Renders the host where the count reaches two — a lone town or crown is the panel's own, and a nought tells nothing. Structural, so no `@if` is spent.
@Directive({ selector: '[appPlural]' })
export class PluralDirective {

  private readonly _template = inject(TemplateRef<unknown>);
  private readonly _view = inject(ViewContainerRef);

  public readonly appPlural = input.required<number | undefined>();

  constructor() {
    effect(() => {
      this._view.clear();
      if ((this.appPlural() ?? 0) > 1) this._view.createEmbeddedView(this._template);
    });
  }

}

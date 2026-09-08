import { Directive, effect, inject, input, TemplateRef, ViewContainerRef } from '@angular/core';

// Renders the host where the value exists — `*ngIf` drops a share reading 0, only `undefined` saying « nothing to tell ». Structural, so a panel spends no `@if`.
@Directive({ selector: '[appPresent]' })
export class PresentDirective {

  private readonly _template = inject(TemplateRef<unknown>);
  private readonly _view = inject(ViewContainerRef);

  public readonly appPresent = input.required<unknown>();

  constructor() {
    effect(() => {
      this._view.clear();
      if (this.appPresent() !== undefined) this._view.createEmbeddedView(this._template);
    });
  }

}

import { AfterViewInit, Directive, ElementRef, inject, Renderer2 } from '@angular/core';

// Promote the host's row to a section-header banner — `colspan='2'` on label + remove content cell (CSS can't stretch a TD across table-row columns).
@Directive({ selector: '[appSectionRow]' })
export class SectionRowDirective implements AfterViewInit {

  private readonly _elementRef = inject(ElementRef);
  private readonly _renderer = inject(Renderer2);

  public ngAfterViewInit(): void {
    const tr = (this._elementRef.nativeElement as HTMLElement).closest('tr');
    if (!tr) return;
    const content = tr.querySelector('.ant-descriptions-item-content');
    const label = tr.querySelector('.ant-descriptions-item-label');
    if (label && content) {
      this._renderer.removeChild(content.parentNode, content);
      this._renderer.setAttribute(label, 'colspan', '2');
    }
  }

}

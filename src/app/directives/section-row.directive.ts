import { AfterViewInit, Directive, ElementRef, inject, Renderer2 } from '@angular/core';

// Promote the host's row to a section-header banner — `colspan='2'` on label + remove content cell (CSS can't stretch a TD across table-row columns).
@Directive({ selector: '[appSectionRow]' })
export class SectionRowDirective implements AfterViewInit {

  private readonly _elementRef = inject(ElementRef);
  private readonly _renderer = inject(Renderer2);

  ngAfterViewInit(): void {
    const tr = (this._elementRef.nativeElement as HTMLElement).closest('tr');
    if (!tr) return;
    const content = tr.querySelector(':scope .ant-descriptions-item-content');
    const label = tr.querySelector(':scope .ant-descriptions-item-label');
    if (label && content) {
      // Sum label+content colspans so the label fills the full row regardless of `nzColumn`.
      const span = (Number(label.getAttribute('colspan')) || 1) + (Number(content.getAttribute('colspan')) || 1);
      this._renderer.removeChild(content.parentNode, content);
      this._renderer.setAttribute(label, 'colspan', String(span));
      this._renderer.addClass(label, 'section-header');
    }
  }

}

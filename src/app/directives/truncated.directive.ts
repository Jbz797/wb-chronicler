import { Directive, effect, ElementRef, inject, signal } from '@angular/core';

// Tells whether the host's text is actually clipped, so a tag can offer its full name on hover only where the plate is too narrow to show it.
@Directive({ selector: '[appTruncated]', exportAs: 'appTruncated' })
export class TruncatedDirective {

  public readonly isTruncated = signal(false);

  constructor() {
    const host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;

    // Measured on every resize rather than on hover: a plate is clipped by its own width, which the panel settles long before the pointer arrives.
    effect((onCleanup) => {
      const measure = (): void => this.isTruncated.set(host.scrollWidth > host.clientWidth);
      const resize = new ResizeObserver(measure);
      resize.observe(host);
      measure();
      onCleanup(() => resize.disconnect());
    });
  }

}

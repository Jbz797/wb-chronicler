import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { MarkdownComponent } from 'ngx-markdown';
import { map } from 'rxjs';

import { findPage } from '../constants';

@Component({
  selector: 'app-reader',
  imports: [MarkdownComponent],
  templateUrl: './reader.html',
  styleUrl: './reader.scss',
  host: { '(click)': 'onClick($event)' },
})
export class ReaderComponent {

  private readonly _slug = toSignal(inject(ActivatedRoute).paramMap.pipe(map(p => p.get('slug'))), { requireSync: true });
  protected readonly src = computed(() => findPage(this._slug()).src);

  // Scroll to internal anchors programmatically (bypasses <base href> redirect; suffix match handles invisible-char prefixes like emoji VS-16).
  protected onClick(event: MouseEvent): void {
    const link = (event.target as HTMLElement).closest('a');

    const href = link?.getAttribute('href');
    if (!href?.startsWith('#')) return;

    event.preventDefault();

    const slug = decodeURIComponent(href.slice(1));
    document.querySelector(`[id$="${slug}"]`)?.scrollIntoView({ behavior: 'smooth' });
  }

}

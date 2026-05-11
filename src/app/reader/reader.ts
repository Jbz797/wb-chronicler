import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { MarkdownComponent } from 'ngx-markdown';
import { map } from 'rxjs';

import { PAGES } from '../constants';
import { ChroniclerService } from '../services/chronicler.service';

@Component({
  selector: 'app-reader',
  imports: [MarkdownComponent],
  templateUrl: './reader.html',
  styleUrl: './reader.scss',
  host: { '(click)': 'onClick($event)' },
})
export class ReaderComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _slug = toSignal(inject(ActivatedRoute).paramMap.pipe(map(p => p.get('slug'))), { requireSync: true });

  protected readonly src = computed(() => {
    const slug = this._slug();
    return (PAGES.find(p => p.slug === slug) ?? this._chronicler.chapters().find(c => c.slug === slug) ?? PAGES[0]!).mdUrl;
  });

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

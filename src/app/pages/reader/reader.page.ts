import { Component, computed, ElementRef, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { MarkdownComponent } from 'ngx-markdown';
import { map } from 'rxjs';

import { PAGES } from '../../constants';
import { ActorSpriteHelpers, BookSpriteHelpers, ClanSpriteHelpers, CultureSpriteHelpers, KingdomSpriteHelpers, SubspeciesSpriteHelpers } from '../../helpers';
import { ChroniclerService, RegistryService } from '../../services';

@Component({
  selector: 'app-reader',
  imports: [MarkdownComponent],
  templateUrl: './reader.page.html',
  styleUrl: './reader.page.scss',
  host: { '(click)': 'onClick($event)' },
})
export class ReaderPage {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _element = inject(ElementRef<HTMLElement>);
  private readonly _registry = inject(RegistryService);

  private readonly _slug = toSignal(inject(ActivatedRoute).paramMap.pipe(map(p => p.get('slug'))), { requireSync: true });

  // `undefined` while a chapter slug is still being discovered — avoids flashing/locking onto the Chronicler fallback on refresh.
  protected readonly src = computed(() => {
    const slug = this._slug();
    const page = PAGES.find(p => p.slug === slug) ?? this._chronicler.chapters().find(c => c.slug === slug);
    return page?.mdUrl;
  });

  // Scroll to internal anchors programmatically (bypasses <base href> redirect; suffix match handles invisible-char prefixes like emoji VS-16).
  protected onClick(event: MouseEvent): void {
    const link = (event.target as HTMLElement).closest('a');

    const href = link?.getAttribute('href');
    if (!href?.startsWith('#')) return;

    event.preventDefault();

    const slug = decodeURIComponent(href.slice(1));
    document.querySelector(`[id$="${CSS.escape(slug)}"]`)?.scrollIntoView({ behavior: 'smooth' });
  }

  // Fills the canvas placeholders `marked` left in the prose — subjects and heraldry alike — now that the rendered chapter sits in the DOM.
  protected onReady(): void {
    const root = this._element.nativeElement;
    ActorSpriteHelpers.paintAll(root, this._registry.persons());
    BookSpriteHelpers.paintAll(root, this._registry.books());
    KingdomSpriteHelpers.paintAll(root, this._registry.kingdoms());
    ClanSpriteHelpers.paintAll(root, this._registry.clans());
    CultureSpriteHelpers.paintAll(root, this._registry.cultures());
    SubspeciesSpriteHelpers.paintAll(root, this._registry.subspecies());
  }

}

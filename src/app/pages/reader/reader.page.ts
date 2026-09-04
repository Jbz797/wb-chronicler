import { afterNextRender, Component, computed, effect, ElementRef, inject, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';

import { TranslatePipe } from '@ngx-translate/core';
import { MarkdownComponent } from 'ngx-markdown';
import { NgScrollbar, NgScrollbarModule } from 'ngx-scrollbar';
import { map } from 'rxjs';

import { BOOT_SETTINGS, PAGES } from '../../constants';
import {
  ActorSpriteHelpers, AllianceSpriteHelpers, BookSpriteHelpers, ClanSpriteHelpers, CultureSpriteHelpers, KingdomSpriteHelpers, LanguageSpriteHelpers,
  ReligionSpriteHelpers, SubspeciesSpriteHelpers,
} from '../../helpers';
import { ChroniclerService, RegistryService } from '../../services';

@Component({
  selector: 'app-reader',
  imports: [MarkdownComponent, NgScrollbarModule, TranslatePipe],
  templateUrl: './reader.page.html',
  styleUrl: './reader.page.scss',
  host: { '(click)': 'onClick($event)' },
})
export class ReaderPage {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _dev = inject(BOOT_SETTINGS).dev;
  private readonly _element = inject(ElementRef<HTMLElement>);
  private readonly _registry = inject(RegistryService);
  private readonly _router = inject(Router);
  private readonly _slug = toSignal(inject(ActivatedRoute).paramMap.pipe(map(p => p.get('slug'))), { requireSync: true });

  // Nothing to read and nothing coming: the world is set up but no chapter written yet, so the page says how to open the one who writes them.
  protected readonly awaitsChronicler = computed(() => this._chronicler.probed() && this._chronicler.chapters().length === 0);
  // `undefined` while a chapter slug is still being discovered — avoids flashing/locking onto the Chronicler fallback on refresh.
  protected readonly src = computed(() => {
    const slug = this._slug();
    const page = (this._dev ? PAGES : []).find(p => p.slug === slug) ?? this._chronicler.chapters().find(c => c.slug === slug);
    return page?.mdUrl;
  });

  private readonly _scroller = viewChild.required(NgScrollbar);

  constructor() {
    // The default redirect, and any Précepte slug, resolve to nothing outside dev mode: the latest chapter takes their place as soon as the probe finds one.
    effect(() => {
      if (this._dev || PAGES.every(page => page.slug !== this._slug())) return;
      const latest = this._chronicler.chapters().at(-1);
      if (latest) this._router.navigate(['/', latest.slug], { replaceUrl: true }).catch(() => {});
    });

    // Kept per page: the dev server reloads on each `.md`, and `ng-scrollbar` emits nothing on scroll — the viewport carrying it is listened to directly, once.
    afterNextRender(() => {
      const viewport = this._scroller().adapter.viewportElement;
      viewport.addEventListener('scroll', () => sessionStorage.setItem(`reader.scroll.${this._slug()}`, String(viewport.scrollTop)));
    });
  }

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
    AllianceSpriteHelpers.paintAll(root, this._registry.alliances());
    ClanSpriteHelpers.paintAll(root, this._registry.clans());
    CultureSpriteHelpers.paintAll(root, this._registry.cultures());
    LanguageSpriteHelpers.paintAll(root, this._registry.languages());
    ReligionSpriteHelpers.paintAll(root, this._registry.religions());
    SubspeciesSpriteHelpers.paintAll(root, this._registry.subspecies());
    this._plainOpening(root);
    this._restoreScroll();
  }

  // A chapter opening shorter than the two-line cap forgoes it — measured, not counted, since chars per line follow the window. A workshop page's is instruction.
  private _plainOpening(root: HTMLElement): void {
    const opening = root.querySelector<HTMLElement>(':scope h1 + p:not(.metadata)');
    if (!opening) return;
    opening.classList.remove('plain-opening'); // the cap shapes the wrap, so the height that decides its fate is measured with it on
    const line = Number.parseFloat(getComputedStyle(opening).lineHeight);
    opening.classList.toggle('plain-opening', opening.getBoundingClientRect().height < line * 2);
  }

  // One frame after the prose lands, which is when the viewport has its full height — the canvas sprites are sized in CSS and never move it afterwards.
  private _restoreScroll(): void {
    const target = Number(sessionStorage.getItem(`reader.scroll.${this._slug()}`) ?? 0);
    if (target <= 0) return;
    const viewport = this._scroller().adapter.viewportElement;
    requestAnimationFrame(() => (viewport.scrollTop = target));
  }

}

import { SlicePipe } from '@angular/common';
import { afterRenderEffect, Component, ElementRef, inject, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

import { NzMenuModule } from 'ng-zorro-antd/menu';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { NgScrollbarModule } from 'ngx-scrollbar';

import { PAGES, TAG_LABELS } from '../../../constants';
import { ChroniclerService } from '../../../services';

@Component({
  selector: 'app-nav',
  imports: [NgScrollbarModule, NzMenuModule, NzTooltipModule, RouterLink, SlicePipe],
  templateUrl: './nav.component.html',
  styleUrl: './nav.component.scss',
})
export class NavComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected chapters = this._chronicler.chapters;
  protected pages = PAGES;
  protected tagLabels = TAG_LABELS;

  private readonly _list = viewChild<ElementRef<HTMLElement>>('chapterList');

  constructor() {
    // Each arrival is another chance to catch an entry that did not exist yet, as is each of `ng-scrollbar`'s own updates once it knows its height.
    afterRenderEffect(() => {
      this.chapters();
      this.revealCurrent();
    });
  }

  // Brings the chapter being read into view. `nearest` moves nothing once it is on screen, so the early passes, on a list still filling in, cost nothing.
  protected revealCurrent = (): void => {
    const slug = this._chronicler.currentChapter()?.slug;
    const entry = slug ? this._list()?.nativeElement.querySelector(`[data-slug="${CSS.escape(slug)}"]`) : null;
    entry?.scrollIntoView({ block: 'nearest' });
  };

  protected tagIconUrl = (tag: string): string => `assets/img/tags/${tag.toLowerCase().replaceAll('_', '-')}.png`;

}

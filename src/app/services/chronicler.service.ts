import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';

import { catchError, EMPTY, expand, filter, map, scan } from 'rxjs';

import { SAVES_DIR } from '../constants';
import { ChroniclerHelpers } from '../helpers';
import { Chapter, ChapterMeta } from '../interfaces';

@Injectable({ providedIn: 'root' })
export class ChroniclerService {

  // Chapter list, dynamically discovered by probing C1, C2, ... until 404. Each chapter's chapter.json is captured during probing.
  public readonly chapters = (() => {
    const http = inject(HttpClient);
    const probeChapter = (n: number) => http.get<ChapterMeta>(`${SAVES_DIR}/C${n}/chapter.json`).pipe(map(meta => ({ meta, n })), catchError(() => EMPTY));

    return toSignal(
      probeChapter(1).pipe(
        expand(({ n }) => probeChapter(n + 1)),
        scan((accumulator: Chapter[], { meta, n }) => [
          ...accumulator,
          {
            label: `C${n} — An ${ChroniclerHelpers.yearFromWorldTime(meta.world_time)}`,
            mdUrl: `${SAVES_DIR}/C${n}/chapter.md`,
            meta,
            previewUrl: `${SAVES_DIR}/C${n}/preview.png`,
            slug: `C${n}`,
          },
        ], []),
      ),
      { initialValue: [] },
    );
  })();
  // Active chapter resolved from the route — re-evaluated on every NavigationEnd.
  public readonly currentChapter = (() => {
    const router = inject(Router);
    const slugFromUrl = (url: string) => (url.split('?')[0] ?? '').replace(/^\//, '');

    const slug = toSignal(router.events.pipe(filter(event => event instanceof NavigationEnd), map(() => slugFromUrl(router.url))));

    return computed(() => this.chapters().find(c => c.slug === slug()));
  })();
  // Chapter just before the current one (by discovery order). `undefined` when current is C1 or not a chapter page.
  public readonly previousChapter = computed(() => {
    const all = this.chapters();
    const index = all.findIndex(c => c.slug === this.currentChapter()?.slug);
    return index > 0 ? all[index - 1] : undefined;
  });

}

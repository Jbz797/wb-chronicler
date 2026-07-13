import { HttpClient } from '@angular/common/http';
import { computed, inject, Service } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';

import { catchError, EMPTY, expand, filter, map, scan } from 'rxjs';

import { SAVES_DIR } from '../constants';
import { Chapter, ChapterMeta } from '../interfaces';

@Service()
export class ChroniclerService {

  private readonly _http = inject(HttpClient);
  private readonly _router = inject(Router);

  // WB convention: 60 `world_time` units = 1 year = 12 in-game months (5 units per month). Returns `month/year` (1-indexed).
  private readonly _dateFromWorldTime = (worldTime: number): string => {
    const year = Math.floor(worldTime / 60) + 1;
    const month = Math.floor((worldTime - (year - 1) * 60) / 5) + 1;
    return `${month}/${year}`;
  };

  // Chapter list, dynamically discovered by probing C1, C2, ... until 404. Each chapter's chapter.json is captured during probing.
  public readonly chapters = (() => {
    const probeChapter = (n: number) => this._http.get<ChapterMeta>(`${SAVES_DIR}/C${n}/chapter.json`).pipe(map(meta => ({ meta, n })), catchError(() => EMPTY));

    return toSignal(
      probeChapter(1).pipe(
        expand(({ n }) => probeChapter(n + 1)),
        scan((accumulator: Chapter[], { meta, n }) => [
          ...accumulator,
          {
            label: `C${n} — ${this._dateFromWorldTime(meta.world.metadata.world_time)}`,
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
    const slugFromUrl = (url: string) => (url.split('?')[0] ?? '').replace(/^\//, '');

    const slug = toSignal(this._router.events.pipe(filter(event => event instanceof NavigationEnd), map(() => slugFromUrl(this._router.url))));

    return computed(() => this.chapters().find(c => c.slug === slug()));
  })();
  // Chapter just before the current one — `undefined` on C1 or non-chapter pages (negative index → `all[-1 or -2]` returns `undefined`).
  public readonly previousChapter = computed(() => {
    const all = this.chapters();
    return all[all.findIndex(c => c.slug === this.currentChapter()?.slug) - 1];
  });

}

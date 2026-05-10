import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { catchError, EMPTY, expand, map, of, scan } from 'rxjs';

import { PAGES, SAVES_DIR } from '../constants';
import { Chapter, ChapterMeta, Page } from '../interfaces';

@Injectable({ providedIn: 'root' })
export class ChroniclerService {

  private readonly _http = inject(HttpClient);

  // Chapter list, dynamically discovered by probing C1, C2, ... until 404. Each chapter's chapter.json is captured during probing.
  public readonly chapters = toSignal(of({ meta: null, n: 0 }).pipe(
    expand(({ n }) => this._http.get<ChapterMeta>(`${SAVES_DIR}/C${n + 1}/chapter.json`).pipe(
      map((m): { meta: ChapterMeta | null; n: number } => ({ meta: m, n: n + 1 })),
      catchError(() => EMPTY),
    )),
    scan((accumulator: Chapter[], { meta, n }) => meta === null ? accumulator : [...accumulator,
      {
        label: `C${n} — An ${Math.floor(meta.world_time / 60) + 1}`,
        mdUrl: `${SAVES_DIR}/C${n}/chapter.md`,
        meta,
        previewUrl: `${SAVES_DIR}/C${n}/preview.png`,
        slug: `C${n}`,
      }], []),
  ), { initialValue: [] });
  public readonly latestChapter = computed(() => this.chapters().at(-1));

  public findPage = (slug: string | null): Page => [...PAGES, ...this.chapters()].find(p => p.slug === slug) ?? PAGES[0]!;

}

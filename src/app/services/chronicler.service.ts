import { HttpClient } from '@angular/common/http';
import { computed, inject, Service, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';

import { catchError, filter, forkJoin, map, Observable, of, tap } from 'rxjs';

import { CHAPTER_INDEX, SAVES_DIR } from '../constants';
import { Chapter, ChapterIndexEntry, ChapterMeta, ChapterTier, LoadedChapter } from '../interfaces';

@Service()
export class ChroniclerService {

  private readonly _http = inject(HttpClient);
  private readonly _router = inject(Router);

  // False until `saves/index.json` has answered — an empty list means « no chapter yet » only once it has, and « not known yet » before.
  public readonly probed = signal(false);
  // Every chapter the index names, in one request. A row carries what the nav prints; the blocks a panel draws are fetched per chapter, by `load`.
  public readonly chapters = toSignal(
    this._http.get<ChapterIndexEntry[]>(CHAPTER_INDEX).pipe(
      map(entries => entries.map(entry => this._row(entry))),
      catchError(() => of<Chapter[]>([])), // no index yet: a world whose first chapter is still to be written
      tap(() => this.probed.set(true)),
    ),
    { initialValue: [] },
  );

  private readonly _slug = toSignal(this._router.events.pipe(filter(event => event instanceof NavigationEnd), map(() => this._slugFromUrl())));

  // The chapter being read, once its blocks are in — `undefined` on a static page, and while the resolver is still fetching them.
  public readonly currentChapter = computed(() => this._loaded(this.chapters().find(c => c.slug === this._slug())));
  // The one before it, which every delta is measured against — `undefined` on C1 and on non-chapter pages.
  public readonly previousChapter = computed(() => {
    const all = this.chapters();
    return this._loaded(all[all.findIndex(c => c.slug === this.currentChapter()?.slug) - 1]);
  });

  // The `chapter.json` of every chapter visited, by slug — written once and never changing, so a second visit costs nothing.
  private readonly _metas = signal<Record<string, ChapterMeta>>({});

  // The body this tier names in the chapter before — same id, same entity, or every delta would compare two strangers: a dead favourite, a crown lost.
  public readonly carriesOver = (tier: ChapterTier): boolean => {
    const previous = this.previousChapter()?.meta[tier]?.metadata;
    const current = this.currentChapter()?.meta[tier]?.metadata;
    return !!previous && !!current && previous.id === current.id;
  };

  // The blocks this chapter and the one before it hold, the panels measuring one against the other. Off the number, not the index, which a cold link outruns.
  public load(slug: string): Observable<unknown> {
    const n = Number(slug.slice(1));
    return forkJoin([this._meta(slug), n > 1 ? this._meta(`C${n - 1}`) : of(null)]);
  }

  // WB convention: 60 `world_time` units = 1 year = 12 in-game months (5 units per month). Returns `month/year` (1-indexed).
  private readonly _dateFromWorldTime = (worldTime: number): string => {
    const year = Math.floor(worldTime / 60) + 1;
    const month = Math.floor((worldTime - (year - 1) * 60) / 5) + 1;
    return `${month}/${year}`;
  };

  private _loaded(chapter: Chapter | undefined): LoadedChapter | undefined {
    const meta = chapter && this._metas()[chapter.slug];
    return chapter && meta ? { ...chapter, meta } : undefined;
  }

  // One chapter's blocks, kept once read. A file that fails to load is not remembered: the next visit is worth another try.
  private _meta(slug: string): Observable<unknown> {
    if (Object.hasOwn(this._metas(), slug)) return of(null);
    return this._http.get<ChapterMeta>(`${SAVES_DIR}/${slug}/chapter.json`).pipe(
      tap(meta => this._metas.update(held => ({ ...held, [slug]: meta }))),
      catchError(() => of(null)),
    );
  }

  private _row(entry: ChapterIndexEntry): Chapter {
    const slug = `C${entry.n}`;
    return {
      label: `${slug} — ${this._dateFromWorldTime(entry.world_time)}`,
      mdUrl: `${SAVES_DIR}/${slug}/chapter.md`,
      previewUrl: `${SAVES_DIR}/${slug}/preview.png`,
      slug,
      tags: entry.tags,
    };
  }

  private _slugFromUrl(): string {
    return (this._router.url.split('?')[0] ?? '').replace(/^\//, '');
  }

}

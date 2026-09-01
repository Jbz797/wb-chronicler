import { HttpClient } from '@angular/common/http';
import { inject, Service, signal, WritableSignal } from '@angular/core';

import { NzMessageService } from 'ng-zorro-antd/message';

import { catchError, forkJoin, Observable, of, tap } from 'rxjs';

import {
  ALLIANCE_REGISTRY, BOOK_REGISTRY, CITY_REGISTRY, CLAN_REGISTRY, CULTURE_REGISTRY, FAMILY_REGISTRY, KINGDOM_REGISTRY, LANGUAGE_REGISTRY, PERSON_REGISTRY,
  RELIGION_REGISTRY, SAVES_DIR, SUBSPECIES_REGISTRY,
} from '../constants';
import {
  AllianceRegistry, BookRegistry, CityRegistry, ClanRegistry, CultureRegistry, FamilyRegistry, KingdomRegistry, LanguageRegistry, PersonRegistry, ReligionRegistry,
  SubspeciesRegistry,
} from '../interfaces';

@Service()
export class RegistryService {

  private readonly _http = inject(HttpClient);
  private readonly _message = inject(NzMessageService);

  public readonly alliances = signal<AllianceRegistry>({});
  public readonly books = signal<BookRegistry>({});
  public readonly cities = signal<CityRegistry>({});
  public readonly clans = signal<ClanRegistry>({});
  public readonly cultures = signal<CultureRegistry>({});
  public readonly families = signal<FamilyRegistry>({});
  public readonly kingdoms = signal<KingdomRegistry>({});
  public readonly languages = signal<LanguageRegistry>({});
  public readonly persons = signal<PersonRegistry>({});
  public readonly religions = signal<ReligionRegistry>({});
  public readonly subspecies = signal<SubspeciesRegistry>({});

  // What each visited chapter's files held, keyed by slug. A chapter's registries are written once and never change, so the second visit costs nothing.
  private readonly _cache = new Map<string, Record<string, object>>();

  // Loads a chapter's registries (per-chapter, period-accurate) into the signals + the marked bridges. Called by the route resolver before the reader renders.
  public load(slug: string): Observable<unknown> {
    if (this._cache.has(slug)) {
      this._swapAll(slug);
      return of(null);
    }
    return forkJoin(this._registries().map(([file, bridge, sig]) => this._load(slug, file, bridge, sig)));
  }

  // Fetch one chapter registry, swap it onto its marked bridge and its signal, and keep it for the next visit. A failed file caches nothing: it is worth retrying.
  private _load(slug: string, file: string, bridge: object, sig: WritableSignal<object>): Observable<unknown> {
    return this._http.get<object>(`${SAVES_DIR}/${slug}/${file}`).pipe(
      tap((data) => {
        this._remember(slug, file, data);
        this._swap(bridge, sig, data);
      }),
      catchError((error: unknown) => {
        const reason = Error.isError(error) ? error.message : 'unknown error';
        this._message.error(`Failed to load ${slug}/${file} — ${reason}`);
        return of(null);
      }),
    );
  }

  // The eleven registries, each with the bridge `marked` reads by reference and the signal the panels read. One table, walked on the way in and on the way back.
  private _registries(): [string, object, WritableSignal<object>][] {
    return [
      ['alliances.json', ALLIANCE_REGISTRY, this.alliances],
      ['books.json', BOOK_REGISTRY, this.books],
      ['cities.json', CITY_REGISTRY, this.cities],
      ['clans.json', CLAN_REGISTRY, this.clans],
      ['cultures.json', CULTURE_REGISTRY, this.cultures],
      ['families.json', FAMILY_REGISTRY, this.families],
      ['kingdoms.json', KINGDOM_REGISTRY, this.kingdoms],
      ['languages.json', LANGUAGE_REGISTRY, this.languages],
      ['persons.json', PERSON_REGISTRY, this.persons],
      ['religions.json', RELIGION_REGISTRY, this.religions],
      ['subspecies.json', SUBSPECIES_REGISTRY, this.subspecies],
    ];
  }

  private _remember(slug: string, file: string, data: object): void {
    this._cache.set(slug, { ...this._cache.get(slug), [file]: data });
  }

  // The bridge is emptied before it takes the new entries: `marked` reads it by reference, and the previous chapter's ids must not linger under the new ones.
  private _swap<T extends object>(bridge: T, sig: WritableSignal<T>, data: T): void {
    Object.keys(bridge).forEach(key => Reflect.deleteProperty(bridge, key));
    Object.assign(bridge, data);
    sig.set(data);
  }

  // A revisited chapter: its files are already in hand, so only the bridges and signals need pointing back at them.
  private _swapAll(slug: string): void {
    const held = this._cache.get(slug) ?? {};
    for (const [file, bridge, sig] of this._registries()) {
      const data = held[file];
      if (data) this._swap(bridge, sig, data);
    }
  }

}

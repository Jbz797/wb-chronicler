import { HttpClient } from '@angular/common/http';
import { inject, Service, signal, WritableSignal } from '@angular/core';

import { NzMessageService } from 'ng-zorro-antd/message';

import { catchError, forkJoin, Observable, of, tap } from 'rxjs';

import { CITY_REGISTRY, KINGDOM_REGISTRY, PERSON_REGISTRY, SAVES_DIR } from '../constants';
import { CityRegistry, KingdomRegistry, PersonRegistry } from '../interfaces';

@Service()
export class RegistryService {

  private readonly _http = inject(HttpClient);
  private readonly _message = inject(NzMessageService);

  public readonly cities = signal<CityRegistry>({});
  public readonly kingdoms = signal<KingdomRegistry>({});
  public readonly persons = signal<PersonRegistry>({});

  // Loads a chapter's three registries (per-chapter, period-accurate) into the signals + the marked bridges. Called by the route resolver before the reader renders.
  public load(slug: string): Observable<unknown> {
    return forkJoin([
      this._load<CityRegistry>(slug, 'cities.json', CITY_REGISTRY, this.cities),
      this._load<KingdomRegistry>(slug, 'kingdoms.json', KINGDOM_REGISTRY, this.kingdoms),
      this._load<PersonRegistry>(slug, 'persons.json', PERSON_REGISTRY, this.persons),
    ]);
  }

  // Fetch one chapter registry, swap it onto its marked bridge (cleared first — the previous chapter's entries mustn't linger) and its reactive signal.
  private _load<T extends object>(slug: string, file: string, bridge: T, sig: WritableSignal<T>): Observable<unknown> {
    return this._http.get<T>(`${SAVES_DIR}/${slug}/${file}`).pipe(
      tap((data) => {
        Object.keys(bridge).forEach(key => Reflect.deleteProperty(bridge, key));
        Object.assign(bridge, data);
        sig.set(data);
      }),
      catchError((error: unknown) => {
        const reason = Error.isError(error) ? error.message : 'unknown error';
        this._message.error(`Failed to load ${slug}/${file} — ${reason}`);
        return of(null);
      }),
    );
  }

}

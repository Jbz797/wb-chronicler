import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';

import { catchError, Observable, of, tap } from 'rxjs';

import { KINGDOM_REGISTRY, SAVES_DIR } from '../constants';
import { KingdomRegistry } from '../interfaces';

@Injectable({ providedIn: 'root' })
export class KingdomRegistryService {

  public readonly registry = signal<KingdomRegistry>({});

  private readonly _http = inject(HttpClient);

  // Fetches the global registry at app init and bridges it to KINGDOM_REGISTRY for the marked renderer.
  public load(): Observable<unknown> {
    return this._http.get<KingdomRegistry>(`${SAVES_DIR}/kingdoms.json`).pipe(tap(data => this._hydrate(data)), catchError(() => of(null)));
  }

  private _hydrate(data: KingdomRegistry): void {
    Object.assign(KINGDOM_REGISTRY, data);
    this.registry.set(data);
  }

}

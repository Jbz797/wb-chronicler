import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal, WritableSignal } from '@angular/core';

import { NzMessageService } from 'ng-zorro-antd/message';

import { catchError, forkJoin, Observable, of, tap } from 'rxjs';

import { KINGDOM_REGISTRY, PERSON_REGISTRY, SAVES_DIR } from '../constants';
import { KingdomRegistry, PersonRegistry } from '../interfaces';

@Injectable({ providedIn: 'root' })
export class RegistryService {

  public readonly kingdoms = signal<KingdomRegistry>({});

  private readonly _http = inject(HttpClient);
  private readonly _message = inject(NzMessageService);

  // Fetches every registry JSON at app init and bridges them to the globals used by the marked renderer.
  public loadAll(): Observable<unknown> {
    return forkJoin([
      this._load<KingdomRegistry>('kingdoms.json', KINGDOM_REGISTRY, this.kingdoms),
      this._load<PersonRegistry>('persons.json', PERSON_REGISTRY),
    ]);
  }

  // Fetch one JSON registry and mirror it onto its global bridge constant. `sig` (optional) also publishes it as a signal, for consumers that read it reactively.
  private _load<T extends object>(file: string, bridge: T, sig?: WritableSignal<T>): Observable<unknown> {
    return this._http.get<T>(`${SAVES_DIR}/${file}`).pipe(
      tap((data) => {
        Object.assign(bridge, data);
        sig?.set(data);
      }),
      catchError((error: unknown) => {
        const reason = Error.isError(error) ? error.message : 'unknown error';
        this._message.error(`Failed to load ${file} — ${reason}`);
        return of(null);
      }),
    );
  }

}

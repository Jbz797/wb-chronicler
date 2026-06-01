import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal, WritableSignal } from '@angular/core';

import { NzMessageService } from 'ng-zorro-antd/message';

import { catchError, forkJoin, Observable, of, tap } from 'rxjs';

import { KINGDOM_REGISTRY, PERSON_REGISTRY, SAVES_DIR } from '../constants';
import { KingdomRegistry, PersonRegistry } from '../interfaces';

@Injectable({ providedIn: 'root' })
export class RegistryService {

  public readonly kingdoms = signal<KingdomRegistry>({});
  public readonly persons = signal<PersonRegistry>({});

  private readonly _http = inject(HttpClient);
  private readonly _message = inject(NzMessageService);

  // Fetches every registry JSON at app init and bridges them to the globals used by the marked renderer.
  public loadAll(): Observable<unknown> {
    return forkJoin([
      this._load<KingdomRegistry>('kingdoms.json', this.kingdoms, KINGDOM_REGISTRY),
      this._load<PersonRegistry>('persons.json', this.persons, PERSON_REGISTRY),
    ]);
  }

  // Fetch one JSON registry, mirror it onto its global bridge constant, and publish it via the signal.
  private _load<T extends object>(file: string, sig: WritableSignal<T>, bridge: T): Observable<unknown> {
    return this._http.get<T>(`${SAVES_DIR}/${file}`).pipe(
      tap((data) => {
        Object.assign(bridge, data);
        sig.set(data);
      }),
      catchError((error: unknown) => {
        const reason = error instanceof Error ? error.message : 'unknown error';
        this._message.error(`Failed to load ${file} — ${reason}`);
        return of(null);
      }),
    );
  }

}

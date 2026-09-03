import { Service } from '@angular/core';

import { TranslateLoader } from '@ngx-translate/core';
import { from, Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// The app's own strings out of `assets/i18n/`, plus the species names from the chronicler's own `world/i18n/` — the one thing his tools never spell out for him.
@Service()
export class TranslateLoaderService implements TranslateLoader {

  public getTranslation(lang: string): Observable<Record<string, string>> {
    return from(this._load(lang)).pipe(
      catchError((error: Error) => {
        // eslint-disable-next-line no-console
        console.warn(`Translation file for language '${lang}' could not be loaded:`, error.message);
        return of({});
      }),
    );
  }

  private async _fetch(path: string): Promise<Record<string, string>> {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Failed to load translation file: ${path}`);
    return response.json() as Promise<Record<string, string>>;
  }

  // Species names live beside the chronicle, keyed by bare asset id so he reads them as he writes his tags; the `species_` prefix is the reader's business.
  private async _load(lang: string): Promise<Record<string, string>> {
    const [app, species] = await Promise.all([
      this._fetch(`./assets/i18n/${lang}.json`),
      this._fetch(`./assets/world/i18n/species.${lang}.json`),
    ]);
    return { ...app, ...Object.fromEntries(Object.entries(species).map(([id, name]) => [`species_${id}`, name])) };
  }

}

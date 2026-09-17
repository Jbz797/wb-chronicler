import { Service } from '@angular/core';

import { TranslateLoader } from '@ngx-translate/core';
import { from, Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// The app's own strings out of `assets/i18n/`, plus the species and age names from the chronicler's own `world/i18n/` — what his tools never spell out for him.
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

  // Species and age names live beside the chronicle, keyed by bare id so he reads them as he writes; the `species_` and `age_` prefixes are the reader's business.
  private async _load(lang: string): Promise<Record<string, string>> {
    const [app, ages, species] = await Promise.all([
      this._fetch(`./assets/i18n/${lang}.json`),
      this._fetch(`./assets/world/i18n/${lang}/ages.json`),
      this._fetch(`./assets/world/i18n/${lang}/species.json`),
    ]);
    return { ...app, ...this._prefixed('age', ages), ...this._prefixed('species', species) };
  }

  // A world file's bare ids, under the prefix the templates translate them by.
  private _prefixed(prefix: string, names: Record<string, string>): Record<string, string> {
    return Object.fromEntries(Object.entries(names).map(([id, name]) => [`${prefix}_${id}`, name]));
  }

}

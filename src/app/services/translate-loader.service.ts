import { Service } from '@angular/core';

import { TranslateLoader } from '@ngx-translate/core';
import { from, Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// Serves a language table out of `assets/i18n/`. A missing file leaves the app running on its keys rather than blank, as a chapter still reads without them.
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

  private async _load(lang: string): Promise<Record<string, string>> {
    const response = await fetch(`./assets/i18n/${lang}.json`);
    if (!response.ok) throw new Error(`Failed to load translation file for language: ${lang}`);
    return response.json() as Promise<Record<string, string>>;
  }

}

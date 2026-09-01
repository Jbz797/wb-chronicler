import { registerLocaleData } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import localeEn from '@angular/common/locales/en-GB';
import localeFr from '@angular/common/locales/fr';
import { inject, LOCALE_ID, provideAppInitializer, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { en_GB, fr_FR, provideNzI18n } from 'ng-zorro-antd/i18n';

import { provideTranslateLoader, provideTranslateService, TranslateService } from '@ngx-translate/core';
import { provideMarkdown } from 'ngx-markdown';
import { provideScrollbarOptions, provideScrollbarPolyfill } from 'ngx-scrollbar';
import { firstValueFrom } from 'rxjs';
import 'prismjs';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-python';

import { App } from './app/app';
import { SETTINGS_FILE } from './app/constants';
import { MarkedHelpers } from './app/helpers';
import { Settings } from './app/interfaces';
import { ROUTES } from './app/routes';
import { TranslateLoaderService } from './app/services';

// The one tongue the chronicle is kept in, off `settings.json` which the chronicler reads too. Until one is set: the browser's where we serve it, English otherwise.
const chosenLanguage = async (): Promise<string> => {
  const available = new Set(['en', 'fr']);
  const browser = globalThis.navigator.language.slice(0, 2);
  const fallback = available.has(browser) ? browser : 'en';
  try {
    const answer = await fetch(SETTINGS_FILE, { cache: 'no-store' });
    const { lang } = answer.ok ? ((await answer.json()) as Settings) : {};
    return lang && available.has(lang) ? lang : fallback;
  } catch {
    return fallback;
  }
};

// Resolved before the app is built: `LOCALE_ID` and ng-zorro's tables are read as the injector is assembled, and both shape a number — `2 556` here, `2,556` there.
const start = async (): Promise<unknown> => {
  const lang = await chosenLanguage();
  const isFrench = lang !== 'en';

  registerLocaleData(isFrench ? localeFr : localeEn);
  document.documentElement.lang = lang; // `hyphens: auto` breaks words by the declared tongue's rules, and the chronicle is justified prose

  MarkedHelpers.configure();

  return bootstrapApplication(App, {
    providers: [
      provideAppInitializer(() => firstValueFrom(inject(TranslateService).use(lang))),
      provideBrowserGlobalErrorListeners(),
      provideHttpClient(),
      provideMarkdown(),
      provideNzI18n(isFrench ? fr_FR : en_GB),
      provideRouter(ROUTES),
      provideScrollbarOptions({ appearance: 'compact', visibility: 'hover' }), // Every scroller alike: painted over the content, not beside it, shown only on hover.
      provideScrollbarPolyfill('assets/scroll-timeline-polyfill.js'), // Served from the app, never a CDN: `scroll-timeline` drives the thumb, and Firefox lacks it.
      provideTranslateService({ loader: provideTranslateLoader(TranslateLoaderService) }),
      provideZoneChangeDetection(),
      { provide: LOCALE_ID, useValue: isFrench ? 'fr-FR' : 'en-GB' },
    ],
  });
};

start().catch((error: unknown) => {
  // eslint-disable-next-line no-console
  console.error(error);
});

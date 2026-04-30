import { registerLocaleData } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import fr from '@angular/common/locales/fr';
import { LOCALE_ID, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';

import { fr_FR, provideNzI18n } from 'ng-zorro-antd/i18n';

import { provideMarkdown } from 'ngx-markdown';
import 'prismjs';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-python';

import { AppComponent } from './app/app';

registerLocaleData(fr);

bootstrapApplication(AppComponent, {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(),
    provideMarkdown(),
    provideNzI18n(fr_FR),
    provideZoneChangeDetection(),
    { provide: LOCALE_ID, useValue: 'fr-FR' },
  ],
}).catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
});

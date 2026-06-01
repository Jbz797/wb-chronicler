import { registerLocaleData } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import fr from '@angular/common/locales/fr';
import { inject, LOCALE_ID, provideAppInitializer, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';

import { fr_FR, provideNzI18n } from 'ng-zorro-antd/i18n';

import { provideMarkdown } from 'ngx-markdown';
import 'prismjs';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-python';

import { App } from './app/app';
import { MarkedHelpers } from './app/helpers';
import { ROUTES } from './app/routes';
import { RegistryService } from './app/services';

registerLocaleData(fr);

MarkedHelpers.configure();

bootstrapApplication(App, {
  providers: [
    provideAppInitializer(() => inject(RegistryService).loadAll()),
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(),
    provideMarkdown(),
    provideNzI18n(fr_FR),
    provideRouter(ROUTES),
    provideZoneChangeDetection(),
    { provide: LOCALE_ID, useValue: 'fr-FR' },
  ],
}).catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
});

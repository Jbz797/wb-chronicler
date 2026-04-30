import { registerLocaleData } from '@angular/common';
import fr from '@angular/common/locales/fr';
import { LOCALE_ID, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';

import { fr_FR, provideNzI18n } from 'ng-zorro-antd/i18n';

import { AppComponent } from './app/app';

registerLocaleData(fr);

bootstrapApplication(AppComponent, {
  providers: [provideBrowserGlobalErrorListeners(), provideNzI18n(fr_FR), provideZoneChangeDetection(), { provide: LOCALE_ID, useValue: 'fr-FR' }],
}).catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
});

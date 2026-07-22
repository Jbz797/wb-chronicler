import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, Routes } from '@angular/router';

import { Observable, of } from 'rxjs';

import { ReaderPage } from './pages/reader/reader.page';
import { RegistryService } from './services';

// Chapter slugs (`C<n>`) load their per-chapter registries before the reader activates, so prose tags + panels resolve against that chapter; static pages skip it.
const registryResolver = (route: ActivatedRouteSnapshot): Observable<unknown> => {
  const slug = route.paramMap.get('slug') ?? '';
  return /^C\d+$/.test(slug) ? inject(RegistryService).load(slug) : of(null);
};

export const ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'chronicler' },
  { component: ReaderPage, path: ':slug', resolve: { registries: registryResolver } },
];

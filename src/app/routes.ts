import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, Routes } from '@angular/router';

import { forkJoin, Observable, of } from 'rxjs';

import { ReaderPage } from './pages/reader/reader.page';
import { ChroniclerService, RegistryService } from './services';

// A chapter slug (`C<n>`) loads its registries and its blocks before the reader activates, so prose tags and panels resolve against it. A static page needs none.
const chapterResolver = (route: ActivatedRouteSnapshot): Observable<unknown> => {
  const slug = route.paramMap.get('slug') ?? '';
  if (!/^C\d+$/.test(slug)) return of(null);
  return forkJoin([inject(RegistryService).load(slug), inject(ChroniclerService).load(slug)]);
};

export const ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'chronicler' },
  { component: ReaderPage, path: ':slug', resolve: { chapter: chapterResolver } },
];

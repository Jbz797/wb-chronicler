import { Routes } from '@angular/router';

import { ReaderPage } from './pages/reader/reader.page';

export const ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'chronicler' },
  { component: ReaderPage, path: ':slug' },
];

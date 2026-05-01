import { Routes } from '@angular/router';

import { ReaderComponent } from './reader/reader';

export const ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'chronicler' },
  { component: ReaderComponent, path: ':slug' },
];

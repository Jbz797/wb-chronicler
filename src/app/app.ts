import { Component } from '@angular/core';

import { ReaderComponent } from './reader/reader';

@Component({
  selector: 'app-root',
  imports: [ReaderComponent],
  templateUrl: './app.html',
})
export class AppComponent {}

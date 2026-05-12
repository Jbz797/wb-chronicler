import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { NzLayoutModule } from 'ng-zorro-antd/layout';

import { MapPreviewComponent, NavComponent, WorldInfoComponent } from './components/layouts';
import { ChroniclerService } from './services/chronicler.service';

@Component({
  selector: 'app-root',
  imports: [MapPreviewComponent, NavComponent, NzLayoutModule, RouterOutlet, WorldInfoComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {

  protected chapters = inject(ChroniclerService).chapters;

}

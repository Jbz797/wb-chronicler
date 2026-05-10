import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { NzLayoutModule } from 'ng-zorro-antd/layout';

import { MapPreviewComponent } from './map-preview/map-preview';
import { NavComponent } from './nav/nav';
import { ChroniclerService } from './services/chronicler.service';
import { WorldInfoComponent } from './world-info/world-info';

@Component({
  selector: 'app-root',
  imports: [MapPreviewComponent, NavComponent, NzLayoutModule, RouterOutlet, WorldInfoComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {

  protected chapters = inject(ChroniclerService).chapters;

}

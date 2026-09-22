import { Component, inject, signal } from '@angular/core';

import { NzModalModule } from 'ng-zorro-antd/modal';

import { ChroniclerService } from '../../../services';

import { WorldMapComponent } from './world-map/world-map.component';

@Component({
  selector: 'app-map-preview',
  imports: [NzModalModule, WorldMapComponent],
  templateUrl: './map-preview.component.html',
  styleUrl: './map-preview.component.scss',
})
export class MapPreviewComponent {

  protected currentChapter = inject(ChroniclerService).currentChapter;

  protected readonly zoomed = signal(false);

}

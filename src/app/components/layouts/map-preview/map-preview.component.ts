import { Component, inject } from '@angular/core';

import { ChroniclerService } from '../../../services';

@Component({
  selector: 'app-map-preview',
  templateUrl: './map-preview.component.html',
  styleUrl: './map-preview.component.scss',
})
export class MapPreviewComponent {

  protected currentChapter = inject(ChroniclerService).currentChapter;

}

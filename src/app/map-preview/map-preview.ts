import { Component, inject } from '@angular/core';

import { ChroniclerService } from '../services/chronicler.service';

@Component({
  selector: 'app-map-preview',
  templateUrl: './map-preview.html',
  styleUrl: './map-preview.scss',
})
export class MapPreviewComponent {

  protected latestChapter = inject(ChroniclerService).latestChapter;

}

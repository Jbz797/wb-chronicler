import { HttpClient } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { HISTORY_DIR } from '../constants';
import { World } from '../interfaces';
import { ChroniclerService } from '../services/chronicler.service';

@Component({
  selector: 'app-world-info',
  templateUrl: './world-info.html',
  styleUrl: './world-info.scss',
})
export class WorldInfoComponent {

  protected latestChapter = inject(ChroniclerService).latestChapter;

  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));

}

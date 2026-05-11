import { HttpClient } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';

import { HISTORY_DIR } from '../constants';
import { World } from '../interfaces';
import { ChroniclerService } from '../services/chronicler.service';

@Component({
  selector: 'app-world-info',
  imports: [NzDescriptionsModule, NzDividerModule],
  templateUrl: './world-info.html',
  styleUrl: './world-info.scss',
})
export class WorldInfoComponent {

  protected currentChapter = inject(ChroniclerService).currentChapter;

  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));

}

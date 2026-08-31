import { Component, computed, inject } from '@angular/core';

import { ChroniclerService } from '../../../../services';

import { WarCardComponent } from './war-card/war-card.component';

@Component({
  selector: 'app-wars',
  imports: [WarCardComponent],
  templateUrl: './wars.component.html',
})
export class WarsComponent {

  private readonly _chronicler = inject(ChroniclerService);

  // Every war the favourite's crown is drawn into, oldest first — WB gives an id in the order they were declared.
  protected readonly wars = computed(() => this._chronicler.currentChapter()?.meta.wars ?? []);

}

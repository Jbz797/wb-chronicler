import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { ChroniclerService } from '../../../../services/chronicler.service';

@Component({
  selector: 'app-kingdom',
  imports: [NzDescriptionsModule, NzEmptyModule],
  templateUrl: './kingdom.component.html',
  styleUrl: './kingdom.component.scss',
})
export class KingdomComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly kingdom = computed(() => this._chronicler.currentChapter()?.meta.kingdom ?? null);

}

import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { ChroniclerService } from '../../../../services';

@Component({
  selector: 'app-kingdom',
  imports: [NzDescriptionsModule, NzEmptyModule],
  templateUrl: './kingdom.component.html',
})
export class KingdomComponent {

  protected readonly kingdom = (() => {
    const { currentChapter } = inject(ChroniclerService);
    return computed(() => currentChapter()?.meta.kingdom ?? null);
  })();

}

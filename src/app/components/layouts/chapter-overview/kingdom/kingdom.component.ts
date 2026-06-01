import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { ChroniclerService } from '../../../../services';
import { RankedStatComponent } from '../../../misc';

@Component({
  selector: 'app-kingdom',
  imports: [NzDescriptionsModule, RankedStatComponent],
  templateUrl: './kingdom.component.html',
})
export class KingdomComponent {

  protected readonly kingdom = (() => {
    const { currentChapter } = inject(ChroniclerService);
    return computed(() => currentChapter()?.meta.kingdom ?? null);
  })();

}

import { Component, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { CompactPipe, ExactPipe } from '../../../../pipes';

@Component({
  selector: 'app-delta',
  imports: [CompactPipe, ExactPipe, NzTagModule, NzTooltipModule],
  templateUrl: './delta.component.html',
})
export class DeltaComponent {

  public readonly inverted = input<boolean>(false);
  public readonly suffix = input<string>('');
  public readonly value = input.required<number | undefined>();

}

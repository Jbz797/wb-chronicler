import { Component, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { CompactPipe } from '../../../pipes';

@Component({
  selector: 'app-delta',
  imports: [CompactPipe, NzTagModule],
  templateUrl: './delta.component.html',
})
export class DeltaComponent {

  public readonly inverted = input<boolean>(false);
  public readonly suffix = input<string>('');
  public readonly value = input.required<number | undefined>();

}

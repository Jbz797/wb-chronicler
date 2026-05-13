import { Component, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

@Component({
  selector: 'app-delta',
  imports: [NzTagModule],
  templateUrl: './delta.component.html',
})
export class DeltaComponent {

  public readonly inverted = input<boolean>(false);
  public readonly value = input.required<number | undefined>();

}

import { Component, input } from '@angular/core';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzTagModule } from 'ng-zorro-antd/tag';

@Component({
  selector: 'app-new-badge',
  imports: [NzBadgeModule, NzTagModule],
  templateUrl: './new-badge.component.html',
  styleUrl: './new-badge.component.scss',
})
export class NewBadgeComponent {

  public readonly dot = input<boolean>(true); // A dot ends a label, where a row has no width to spare; the worded plate suits a heading of its own.
  public readonly show = input<boolean>(true);

}

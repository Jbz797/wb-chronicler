import { Component, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

@Component({
  selector: 'app-new-badge',
  imports: [NzTagModule],
  template: '@if (show()) { <nz-tag nzColor="gold">NEW</nz-tag> }',
})
export class NewBadgeComponent {

  public readonly show = input<boolean>(true);

}

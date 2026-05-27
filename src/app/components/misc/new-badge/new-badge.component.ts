import { Component } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

@Component({
  selector: 'app-new-badge',
  imports: [NzTagModule],
  template: '<nz-tag nzColor="gold">NEW</nz-tag>',
})
export class NewBadgeComponent {}

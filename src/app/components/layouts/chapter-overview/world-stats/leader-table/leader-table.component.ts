import { Component, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { NewBadgeComponent } from '../..';
import { LeaderRow } from '../../../../../interfaces';
import { LeaderRowComponent } from '../leader-row/leader-row.component';

@Component({
  selector: 'app-leader-table',
  imports: [LeaderRowComponent, NewBadgeComponent, NzDescriptionsModule],
  templateUrl: './leader-table.component.html',
})
export class LeaderTableComponent {

  public readonly heading = input.required<string>(); // not `title`: a static attribute of that name lands in the DOM too, raising a native tooltip
  public readonly rows = input.required<{ data: LeaderRow; icon: string; label: string }[]>();

}

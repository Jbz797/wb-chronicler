import { Component, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { LeaderRow } from '../../../../../interfaces';
import { LeaderRowComponent } from '../leader-row/leader-row.component';

@Component({
  selector: 'app-leader-table',
  imports: [LeaderRowComponent, NzDescriptionsModule],
  templateUrl: './leader-table.component.html',
})
export class LeaderTableComponent {

  public readonly rows = input.required<{ data: LeaderRow; icon: string; label: string }[]>();
  public readonly title = input.required<string>();

}

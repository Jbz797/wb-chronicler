import { Component, inject } from '@angular/core';

import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { ChroniclerService } from '../../../services';

@Component({
  selector: 'app-sider-actions',
  imports: [NzButtonModule, NzTooltipModule],
  templateUrl: './sider-actions.component.html',
  styleUrl: './sider-actions.component.scss',
})
export class SiderActionsComponent {

  protected chapters = inject(ChroniclerService).chapters;

}

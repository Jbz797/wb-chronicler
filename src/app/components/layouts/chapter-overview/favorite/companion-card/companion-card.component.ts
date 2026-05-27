import { Component, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { ChapterMeta } from '../../../../../interfaces';

@Component({
  selector: 'app-companion-card',
  imports: [NzDescriptionsModule, NzTagModule],
  templateUrl: './companion-card.component.html',
})
export class CompanionCardComponent {

  public readonly data = input.required<NonNullable<NonNullable<ChapterMeta['favorite']>['lover']> | null>();
  public readonly isNew = input.required<boolean>();
  public readonly title = input.required<string>();

}

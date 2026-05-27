import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { ChapterMeta } from '../../../../../interfaces';
import { ChroniclerService } from '../../../../../services/chronicler.service';

@Component({
  selector: 'app-companion-card',
  imports: [NzDescriptionsModule, NzTagModule],
  templateUrl: './companion-card.component.html',
})
export class CompanionCardComponent {

  public readonly data = input.required<NonNullable<NonNullable<ChapterMeta['favorite']>['lover']> | null>();
  public readonly field = input.required<'best_friend' | 'lover'>();
  public readonly title = input.required<string>();

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly isNew = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    const current = this.data();
    if (!previous || !current) return false;
    return current.id !== previous[this.field()]?.id;
  });

}

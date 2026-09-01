import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { NewBadgeComponent } from '../..';
import { TierPipe } from '../../../../../pipes';
import { ChroniclerService } from '../../../../../services';
import { CityTagComponent, KingdomTagComponent } from '../../tags';

@Component({
  selector: 'app-boat-card',
  imports: [CityTagComponent, DecimalPipe, KingdomTagComponent, NewBadgeComponent, NzDescriptionsModule, TierPipe, TranslatePipe],
  templateUrl: './boat-card.component.html',
})
export class BoatCardComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _translate = inject(TranslateService);

  public readonly isNew = input.required<boolean>();

  protected readonly boat = computed(() => this._chronicler.currentChapter()?.meta.boat ?? null);
  // The hull's own name where WB gave it one — barely a tenth of a world's boats are ever named, and a nameless one is simply the favorite's boat.
  protected readonly title = computed(() => this.boat()?.identity.name ?? (this._translate.instant('ui_her_boat') as string));

}

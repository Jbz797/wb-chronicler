import { Component, computed, input } from '@angular/core';

import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'app-inventory',
  imports: [NzTooltipModule, TranslatePipe],
  templateUrl: './inventory.component.html',
})
export class InventoryComponent {

  public readonly resources = input.required<Record<string, number>>();

  protected readonly entries = computed(() => Object.entries(this.resources()).map(([key, amount]) => ({ amount, key })));

}

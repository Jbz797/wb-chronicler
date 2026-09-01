import { Component, computed, input } from '@angular/core';

import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'app-inventory',
  imports: [TranslatePipe],
  templateUrl: './inventory.component.html',
})
export class InventoryComponent {

  public readonly resources = input.required<Record<string, number>>();

  protected readonly entries = computed(() => Object.entries(this.resources()).map(([key, amount]) => ({ amount, key })));

}

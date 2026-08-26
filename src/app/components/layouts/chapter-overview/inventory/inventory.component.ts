import { Component, computed, input } from '@angular/core';

@Component({
  selector: 'app-inventory',
  templateUrl: './inventory.component.html',
})
export class InventoryComponent {

  public readonly resources = input.required<Record<string, number>>();

  protected readonly entries = computed(() => Object.entries(this.resources()).map(([key, amount]) => ({ amount, key })));

}

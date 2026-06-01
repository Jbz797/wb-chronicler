import { Component, computed, inject, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { RegistryService } from '../../../services';

@Component({
  selector: 'app-kingdom-tag',
  imports: [NzTagModule],
  templateUrl: './kingdom-tag.component.html',
})
export class KingdomTagComponent {

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  protected readonly kingdom = (() => {
    const { kingdoms } = inject(RegistryService);
    return computed(() => kingdoms()[String(this.id())] ?? null);
  })();

}

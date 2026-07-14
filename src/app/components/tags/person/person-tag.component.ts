import { Component, computed, input } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { SPECIES_COLORS } from '../../../constants';

@Component({
  selector: 'app-person-tag',
  imports: [NzTagModule],
  templateUrl: './person-tag.component.html',
})
export class PersonTagComponent {

  public readonly assetId = input.required<string>();
  public readonly dead = input<boolean>(false);
  public readonly name = input.required<string>();
  public readonly profession = input<string>('');
  public readonly sex = input<string>('');

  protected readonly color = computed(() => SPECIES_COLORS[this.assetId()] ?? null);

}

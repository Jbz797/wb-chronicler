import { Component, computed, effect, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TruncatedDirective } from '../../../../../directives';
import { AllianceSpriteHelpers, PaletteHelpers } from '../../../../../helpers';
import { RegistryService } from '../../../../../services';

@Component({
  selector: 'app-alliance-tag',
  imports: [NzTagModule, NzTooltipModule, TruncatedDirective],
  templateUrl: './alliance-tag.component.html',
})
export class AllianceTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  protected readonly alliance = computed(() => this._registry.alliances()[String(this.id())] ?? null); // palette, heraldry and species, `null` until registered
  protected readonly color = computed(() => PaletteHelpers.liftedText(this.alliance()?.color)); // its own hue: a pact answers to none of its members

  private readonly _banner = viewChild<ElementRef<HTMLCanvasElement>>('banner'); // absent until `@if (alliance())` has drawn the plate

  constructor() {
    effect(() => {
      const canvas = this._banner()?.nativeElement;
      const alliance = this.alliance();
      if (canvas && alliance) AllianceSpriteHelpers.paint(canvas, alliance).catch(() => {}); // a missing sprite leaves it collapsed
    });
  }

}

import { Component, computed, effect, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TruncatedDirective } from '../../../../../directives';
import { KingdomSpriteHelpers, PaletteHelpers } from '../../../../../helpers';
import { RegistryService } from '../../../../../services';

@Component({
  selector: 'app-kingdom-tag',
  imports: [NzTagModule, NzTooltipModule, TruncatedDirective],
  templateUrl: './kingdom-tag.component.html',
})
export class KingdomTagComponent {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly medal = input(true); // Podium medal shown by default; hidden in the world « Palmarès » where the kingdom is always the winner (gold, redundant).
  public readonly name = input.required<string>();

  protected readonly color = computed(() => PaletteHelpers.realmText(this.id()));
  protected readonly kingdom = computed(() => this._registry.kingdoms()[String(this.id())] ?? null); // palette, heraldry and species, `null` until registered

  private readonly _banner = viewChild<ElementRef<HTMLCanvasElement>>('banner'); // absent until `@if (kingdom())` has drawn the plate

  constructor() {
    effect(() => {
      const canvas = this._banner()?.nativeElement;
      const kingdom = this.kingdom();
      if (canvas && kingdom) KingdomSpriteHelpers.paint(canvas, kingdom).catch(() => {}); // a species with no banner set leaves it collapsed
    });
  }

}

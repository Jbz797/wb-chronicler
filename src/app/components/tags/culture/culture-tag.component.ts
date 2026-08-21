import { AfterViewInit, Component, computed, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { CultureSpriteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-culture-tag',
  imports: [NzTagModule],
  templateUrl: './culture-tag.component.html',
})
export class CultureTagComponent implements AfterViewInit {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly medal = input(true); // Podium medal shown by default; hidden in the world « Palmarès » where the culture is always the winner (gold, redundant).
  public readonly name = input.required<string>();

  // Hue, founder's species and headcount come from the cultures registry, rebuilt each chapter. `null` until the culture is registered.
  protected readonly culture = computed(() => this._registry.cultures()[String(this.id())] ?? null);

  private readonly _canvas = viewChild<ElementRef<HTMLCanvasElement>>('emblem');

  ngAfterViewInit(): void {
    const canvas = this._canvas()?.nativeElement;
    const culture = this.culture();
    if (canvas && culture) CultureSpriteHelpers.paint(canvas, culture).catch(() => {}); // a missing sprite leaves it collapsed
  }

}

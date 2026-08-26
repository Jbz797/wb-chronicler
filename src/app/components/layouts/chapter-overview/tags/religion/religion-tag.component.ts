import { AfterViewInit, Component, computed, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TruncatedDirective } from '../../../../../directives';
import { ReligionSpriteHelpers } from '../../../../../helpers';
import { RegistryService } from '../../../../../services';

@Component({
  selector: 'app-religion-tag',
  imports: [NzTagModule, NzTooltipModule, TruncatedDirective],
  templateUrl: './religion-tag.component.html',
})
export class ReligionTagComponent implements AfterViewInit {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly medal = input(true); // Podium medal shown by default; hidden in the world « Palmarès » where the creed is always the winner (gold, redundant).
  public readonly name = input.required<string>();

  // Hue, founder's species and headcount come from the religions registry, rebuilt each chapter. `null` until the religion is registered.
  protected readonly religion = computed(() => this._registry.religions()[String(this.id())] ?? null);

  private readonly _canvas = viewChild<ElementRef<HTMLCanvasElement>>('emblem');

  ngAfterViewInit(): void {
    const canvas = this._canvas()?.nativeElement;
    const religion = this.religion();
    if (canvas && religion) ReligionSpriteHelpers.paint(canvas, religion).catch(() => {}); // a missing sprite leaves it collapsed
  }

}

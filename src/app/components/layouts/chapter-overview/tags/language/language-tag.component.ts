import { AfterViewInit, Component, computed, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TruncatedDirective } from '../../../../../directives';
import { LanguageSpriteHelpers } from '../../../../../helpers';
import { RegistryService } from '../../../../../services';

@Component({
  selector: 'app-language-tag',
  imports: [NzTagModule, NzTooltipModule, TruncatedDirective],
  templateUrl: './language-tag.component.html',
})
export class LanguageTagComponent implements AfterViewInit {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly medal = input(true); // Podium medal shown by default; hidden in the world « Palmarès » where the tongue is always the winner (gold, redundant).
  public readonly name = input.required<string>();

  // Hue, founder's species and speaker count come from the languages registry, rebuilt each chapter. `null` until the language is registered.
  protected readonly language = computed(() => this._registry.languages()[String(this.id())] ?? null);

  private readonly _canvas = viewChild<ElementRef<HTMLCanvasElement>>('emblem');

  ngAfterViewInit(): void {
    const canvas = this._canvas()?.nativeElement;
    const language = this.language();
    if (canvas && language) LanguageSpriteHelpers.paint(canvas, language).catch(() => {}); // a missing sprite leaves it collapsed
  }

}

import { AfterViewInit, Component, computed, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { SubspeciesSpriteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-subspecies-tag',
  imports: [NzTagModule],
  templateUrl: './subspecies-tag.component.html',
})
export class SubspeciesTagComponent implements AfterViewInit {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // Slab, bookmark hues, species pip and living bearers come from the subspecies registry, rebuilt each chapter. `null` until the biology is registered.
  protected readonly subspecies = computed(() => this._registry.subspecies()[String(this.id())] ?? null);
  protected readonly slab = computed(() => SubspeciesSpriteHelpers.slab(this.subspecies()?.banner_bg));

  private readonly _canvas = viewChild<ElementRef<HTMLCanvasElement>>('bookmark');

  ngAfterViewInit(): void {
    const canvas = this._canvas()?.nativeElement;
    const subspecies = this.subspecies();
    if (canvas && subspecies) SubspeciesSpriteHelpers.paint(canvas, subspecies).catch(() => {}); // a biology with no colour leaves it collapsed
  }

}

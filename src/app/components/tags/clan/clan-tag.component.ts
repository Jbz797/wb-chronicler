import { AfterViewInit, Component, computed, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { ClanSpriteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-clan-tag',
  imports: [NzTagModule],
  templateUrl: './clan-tag.component.html',
})
export class ClanTagComponent implements AfterViewInit {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly medal = input(true); // Podium medal shown by default; hidden where the entity is the winner by construction.
  public readonly name = input.required<string>();

  // Hue, founder's species and headcount come from the clans registry, rebuilt each chapter. `null` until the clan is registered.
  protected readonly clan = computed(() => this._registry.clans()[String(this.id())] ?? null);

  private readonly _canvas = viewChild<ElementRef<HTMLCanvasElement>>('banner');

  ngAfterViewInit(): void {
    const canvas = this._canvas()?.nativeElement;
    const clan = this.clan();
    if (canvas && clan) ClanSpriteHelpers.paint(canvas, clan).catch(() => {}); // a species with no banner set leaves it collapsed
  }

}

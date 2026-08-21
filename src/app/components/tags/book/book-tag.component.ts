import { AfterViewInit, Component, computed, ElementRef, inject, input, viewChild } from '@angular/core';

import { NzTagModule } from 'ng-zorro-antd/tag';

import { BookSpriteHelpers } from '../../../helpers';
import { RegistryService } from '../../../services';

@Component({
  selector: 'app-book-tag',
  imports: [NzTagModule],
  templateUrl: './book-tag.component.html',
})
export class BookTagComponent implements AfterViewInit {

  private readonly _registry = inject(RegistryService);

  public readonly id = input.required<number>();
  public readonly name = input.required<string>();

  // Cover, glyph, genre hue and readings come from the books registry, rebuilt each chapter. `null` until the volume is registered.
  protected readonly book = computed(() => this._registry.books()[String(this.id())] ?? null);

  private readonly _canvas = viewChild<ElementRef<HTMLCanvasElement>>('board');

  ngAfterViewInit(): void {
    const canvas = this._canvas()?.nativeElement;
    const book = this.book();
    if (canvas && book) BookSpriteHelpers.paint(canvas, book).catch(() => {}); // a missing sheet leaves it collapsed
  }

}

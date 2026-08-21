import { BookInfo } from '../../interfaces';

import { SpriteHelpers } from './sprite.helpers';

// A volume's sprite, WB `CultureBookButton.load`: one of twenty cover sheets under its genre's white glyph, neither tinted — a book's hue is its title's.
export class BookSpriteHelpers {

  private static readonly _volumes = new Map<string, Promise<HTMLCanvasElement | null>>();

  public static paint = async (canvas: HTMLCanvasElement, book: BookInfo): Promise<void> => SpriteHelpers.blit(canvas, await this._compose(book));

  public static paintAll(root: ParentNode, books: Record<string, BookInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'book', books, (canvas, book) => this.paint(canvas, book));
  }

  // The cover sizes the canvas; the glyph is centred on the boards, a column right of centre to clear the spine and a row up to clear the page edge.
  private static async _build(book: BookInfo): Promise<HTMLCanvasElement | null> {
    const [cover, glyph] = await Promise.all([
      SpriteHelpers.load(`assets/img/books/covers/${book.cover}.png`),
      SpriteHelpers.load(`assets/img/books/icons/${book.icon}.png`),
    ]);
    const cut = document.createElement('canvas');
    cut.height = cover.naturalHeight;
    cut.width = cover.naturalWidth;
    const context = cut.getContext('2d');
    if (!context) return null;

    context.drawImage(cover, 0, 0);
    context.drawImage(glyph, Math.floor((cut.width - glyph.naturalWidth) / 2) + 1, Math.floor((cut.height - glyph.naturalHeight) / 2) - 1);
    return cut;
  }

  // Keyed on the two sheets alone — every volume sharing a cover and a glyph wears the same board, whatever its title.
  private static async _compose(book: BookInfo): Promise<HTMLCanvasElement | null> {
    if (!book.cover || !book.icon) return null;
    return SpriteHelpers.compose(this._volumes, `${book.cover},${book.icon}`, () => this._build(book));
  }

}

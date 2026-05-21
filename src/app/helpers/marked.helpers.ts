import { marked, Tokens } from 'marked';
import { gfmHeadingId } from 'marked-gfm-heading-id';

import { SPECIES_COLORS } from '../constants';
import { IconKind, IconToken, LexerThis, ParserThis } from '../interfaces';

export class MarkedHelpers {

  // Inline icon codes
  public static configure(): void {
    const resourcePattern = this._iconPattern('r');
    const speciesPattern = this._iconPattern('s');

    marked.use(gfmHeadingId());

    marked.use({
      extensions: [
        // `[r <id> <text>?]` = resource (icon + optional text, never colored).
        {
          level: 'inline',
          name: 'resources',
          renderer(token) {
            return MarkedHelpers.render.call(this, token, 'resources', false);
          },
          start: source_ => source_.indexOf('[r '),
          tokenizer(source_) {
            return MarkedHelpers.tokenize.call(this, source_, resourcePattern, 'resources');
          },
        },
        // `[s <id> <text>?]` = species (icon + optional colored text)
        {
          level: 'inline',
          name: 'species',
          renderer(token) {
            return MarkedHelpers.render.call(this, token, 'species', true);
          },
          start: source_ => source_.indexOf('[s '),
          tokenizer(source_) {
            return MarkedHelpers.tokenize.call(this, source_, speciesPattern, 'species');
          },
        },
      ],
    });
  }

  public static render(this: ParserThis, token: Tokens.Generic, folder: string, colorable: boolean): string {
    const { id, tokens: children } = token as IconToken;
    const img = `<img class="icon" src="assets/img/${folder}/${id}.png" />`;
    if (!children?.length) return img;
    const color = colorable ? SPECIES_COLORS[id] : undefined;
    const style = color ? ` style="color: ${color}"` : '';
    return `<span class="icon-wrap"${style}>${this.parser.parseInline(children)}${img}</span>`;
  }

  public static tokenize(this: LexerThis, source_: string, pattern: RegExp, type: IconKind): IconToken | undefined {
    const match = pattern.exec(source_);
    if (!match) return undefined;
    const result: IconToken = { id: match[1]!, raw: match[0], type };
    if (match[2]) {
      result.tokens = [];
      this.lexer.inline(match[2], result.tokens);
    }
    return result;
  }

  private static readonly _iconPattern = (letter: 'r' | 's'): RegExp => new RegExp(String.raw`^\[${letter} ([_a-z]+)(?: ([^\n\]]+))?]`);

}

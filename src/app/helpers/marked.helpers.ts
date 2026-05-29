import { marked, Tokens } from 'marked';
import { gfmHeadingId } from 'marked-gfm-heading-id';

import { KINGDOM_REGISTRY, SPECIES_COLORS } from '../constants';
import { IconKind, IconToken, LexerThis, ParserThis } from '../interfaces';

export class MarkedHelpers {

  // Inline icon codes
  public static configure(): void {
    const kingdomPattern = this._iconPattern('k', { nameOptional: false });
    const resourcePattern = this._iconPattern('r', { nameOptional: true });
    const speciesPattern = this._iconPattern('s', { nameOptional: true });

    marked.use(gfmHeadingId());

    marked.use({
      extensions: [
        // `[k <id> <name>]` = kingdom (colored name + banner icon, resolved from the registry).
        {
          level: 'inline',
          name: 'kingdoms',
          renderer(token) {
            return MarkedHelpers.renderKingdom.call(this, token);
          },
          start: source_ => source_.indexOf('[k '),
          tokenizer(source_) {
            return MarkedHelpers.tokenize.call(this, source_, kingdomPattern, 'kingdoms');
          },
        },
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

  public static renderKingdom(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = KINGDOM_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;
    const crown = '<span class="glyph" style="mask-image: url(assets/img/world/kingdom.png)"></span>';
    const banner = info
      ? `<span class="glyph" style="mask-image: url(assets/img/banners/${info.banner_icon}.png)"></span>`
      : '';
    return `<span class="ant-tag kingdom-tag" style="--kingdom-color: ${info?.color ?? ''}; --kingdom-ink: ${info?.ink ?? ''}">${crown}${name}${banner}</span>`;
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

  // Inline-code regex: numeric id for kingdoms (else `[_a-z]+`), name optional for species/resources.
  private static readonly _iconPattern = (letter: 'k' | 'r' | 's', { nameOptional }: { nameOptional: boolean }): RegExp => {
    const id = letter === 'k' ? String.raw`\d+` : String.raw`[_a-z]+`;
    const name = nameOptional ? String.raw`(?: ([^\n\]]+))?` : String.raw` ([^\n\]]+)`;
    return new RegExp(String.raw`^\[${letter} (${id})${name}]`);
  };

}

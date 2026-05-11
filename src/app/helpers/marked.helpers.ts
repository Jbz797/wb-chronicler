import { marked } from 'marked';
import { gfmHeadingId } from 'marked-gfm-heading-id';

import { SPECIES_COLORS } from '../constants';
import { SpeciesToken } from '../interfaces';

export class MarkedHelpers {

  // One-shot setup at bootstrap
  public static configure(): void {
    // GFM heading IDs
    marked.use(gfmHeadingId());

    // Inline species codes (asset_id = in-game ID, cf. chronicler.md):
    marked.use({
      extensions: [{
        level: 'inline',
        name: 'species',
        renderer(token) {
          const { id, tokens: children } = token as SpeciesToken;
          const img = `<img class="species-icon" src="assets/img/species/${id}.png" />`;
          if (!children?.length) return img;
          const color = SPECIES_COLORS[id];
          const style = color ? ` style="color: ${color}"` : '';
          return `<span class="species"${style}>${img}${this.parser.parseInline(children)}</span>`;
        },
        start: source => source.indexOf(':'),
        tokenizer(source): SpeciesToken | undefined {
          const match = /^:([_a-z]+)(?: ([^\n:]+))?:/.exec(source);
          if (!match) return undefined;
          const result: SpeciesToken = { id: match[1]!, raw: match[0], type: 'species' };
          if (match[2]) {
            result.tokens = [];
            this.lexer.inline(match[2], result.tokens);
          }
          return result;
        },
      }],
    });
  }

}

import { marked, TokenizerAndRendererExtension, Tokens } from 'marked';
import { gfmHeadingId } from 'marked-gfm-heading-id';

import { CHAPTER_REGISTRY, CITY_REGISTRY, INLINE_MARKER, KINGDOM_REGISTRY, PERSON_REGISTRY, SAVES_DIR, SPECIES_COLORS } from '../constants';
import { IconKind, IconToken, InlineMarker, ParserThis } from '../interfaces';

export class MarkedHelpers {

  // Inline icon codes — each one a `[<letter> <id> <name>]` marker handled by its own renderer.
  public static configure(): void {
    marked.use(gfmHeadingId());
    marked.use({
      extensions: [
        // `[c <id> <name>]` = city (settlement glyph + name, coloured by its kingdom's palette from the registry).
        this._extension(INLINE_MARKER.City, 'cities', false, this._renderCity),
        // `[k <id> <name>]` = kingdom (colored name + banner icon, resolved from the registry).
        this._extension(INLINE_MARKER.Kingdom, 'kingdoms', false, this._renderKingdom),
        // `[p <id> <name>]` = person (intelligent only: species icon + name + sex icon, from the registry).
        this._extension(INLINE_MARKER.Person, 'persons', false, this._renderPerson),
        // `[r <id> <text>?]` = resource (icon + optional text, never colored).
        this._extension(INLINE_MARKER.Resource, 'resources', true, this._renderResource),
        // `[s <id> <text>?]` = species (icon + optional colored text).
        this._extension(INLINE_MARKER.Species, 'species', true, this._renderSpecies),
      ],
    });
  }

  // Build a marked inline extension for a `[<letter> <id> <name>]` marker — shared shape across all 5 kinds.
  private static _extension(
    marker: InlineMarker,
    kind: IconKind,
    isNameOptional: boolean,
    renderer: (this: ParserThis, token: Tokens.Generic) => string,
  ): TokenizerAndRendererExtension {
    const pattern = this._iconPattern(marker, { isNameOptional });
    return {
      level: 'inline',
      name: kind,
      renderer(token) {
        return renderer.call(this, token);
      },
      start: source_ => source_.indexOf(`[${marker} `),
      tokenizer(source_): IconToken | undefined {
        const match = pattern.exec(source_);
        if (!match) return undefined;
        const result: IconToken = { id: match[1]!, raw: match[0], type: kind };
        if (match[2]) {
          result.tokens = [];
          this.lexer.inline(match[2], result.tokens);
        }
        return result;
      },
    };
  }

  // Inline-code regex: numeric id for cities/kingdoms/persons (else `[_a-z]+`), name optional per caller.
  private static readonly _iconPattern = (letter: InlineMarker, { isNameOptional }: { isNameOptional: boolean }): RegExp => {
    const isNumericId = letter === INLINE_MARKER.City || letter === INLINE_MARKER.Kingdom || letter === INLINE_MARKER.Person;
    const id = isNumericId ? String.raw`\d+` : '[_a-z]+';
    const name = isNameOptional ? String.raw`(?: ([^\n\]]+))?` : String.raw` ([^\n\]]+)`;
    return new RegExp(String.raw`^\[${letter} (${id})${name}]`);
  };

  private static _renderCity(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = CITY_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;
    // WB crown icon, pre-generated per chapter (kingdom-tinted, capital = gold crown / village = stone rampart). No banner keeps it lighter than its `[k]` realm.
    const crown = `<img class="crown" src="${SAVES_DIR}/${CHAPTER_REGISTRY.slug}/crowns/c${id}.png" />`;
    const size = info?.size ? `<span class="city-size"><span>${info.size}</span></span>` : ''; // Civ-style population-tier badge (1 foyer … 7 métropole).
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const dead = info?.dead ? ' dead' : ''; // razed settlement → drained + struck-through style
    const style = `--city-color: ${info?.color ?? ''}; --city-ink: ${info?.ink ?? ''}`;
    return `<span class="ant-tag entity-tag city-tag${dead}" style="${style}">${crown}<span class="entity-name">${name}</span>${size}${species}</span>`;
  }

  private static _renderKingdom(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = KINGDOM_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;
    const crown = '<span class="glyph" style="mask-image: url(assets/img/world/kingdom.png)"></span>';
    const banner = info
      ? `<span class="glyph" style="mask-image: url(assets/img/banners/${info.banner_icon}.png)"></span>`
      : '';
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const dead = info?.dead ? ' dead' : ''; // destroyed kingdom → drained + struck-through style
    const style = `--kingdom-color: ${info?.color ?? ''}; --kingdom-ink: ${info?.ink ?? ''}`;
    const label = `<span class="entity-name">${name}</span>`;
    return `<span class="ant-tag entity-tag kingdom-tag${dead}" style="${style}">${crown}${label}${banner}${species}</span>`;
  }

  private static _renderPerson(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const name = children?.length ? this.parser.parseInline(children) : id;
    const info = PERSON_REGISTRY[id];
    const color = info && SPECIES_COLORS[info.asset_id];
    if (!info || !color) return name;
    const profession = info.profession ? `<img src="assets/img/professions/${info.profession}.png" />` : '';
    const badge = info.dead ? '<img src="assets/img/world/deaths.png" />' : profession;
    const species = `<img src="assets/img/species/${info.asset_id}.png" />`;
    const sex = info.sex ? `<img src="assets/img/sex/${info.sex}.png" />` : ''; // Folded pre-history founders carry no actor data — no sex to show.
    const label = `<span class="entity-name">${name}</span>`;
    // Order: profession/tombstone · name · sex · species icon (trailing, like kingdom/city tags).
    return `<span class="ant-tag entity-tag person-tag${info.dead ? ' dead' : ''}" style="--person-color: ${color}">${badge}${label}${sex}${species}</span>`;
  }

  // Resource: icon + optional inline text, never coloured.
  private static _renderResource(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const img = `<img class="icon" src="assets/img/resources/${id}.png" />`;
    if (!children?.length) return img;
    return `<span class="icon-wrap">${this.parser.parseInline(children)}${img}</span>`;
  }

  // Species: icon + optional inline text coloured by `SPECIES_COLORS`.
  private static _renderSpecies(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const img = `<img class="icon" src="assets/img/species/${id}.png" />`;
    if (!children?.length) return img;
    const color = SPECIES_COLORS[id];
    const style = color ? ` style="color: ${color}"` : '';
    return `<span class="icon-wrap"${style}>${this.parser.parseInline(children)}${img}</span>`;
  }

}

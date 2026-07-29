import { marked, TokenizerAndRendererExtension, Tokens } from 'marked';
import { gfmHeadingId } from 'marked-gfm-heading-id';

import { CITY_REGISTRY, INLINE_MARKER, KINGDOM_REGISTRY, PERSON_REGISTRY, SPECIES_COLORS } from '../constants';
import { IconKind, IconToken, InlineMarker, ParserThis } from '../interfaces';

import { PaletteHelpers } from './palette.helpers';

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
        // `[p <id> <name>]` = person (portrait painted after render + name + sex icon + charge, from the registry).
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

  // A settlement plate: crown, name, podium medal, size medallion, species glyph — everything but the realm's banner, which keeps it lighter than its `[k]`.
  private static _renderCity(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = CITY_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const crown = `<canvas class="crown" data-city="${id}" height="0" width="0"></canvas>`; // sized to nothing until `paintAll` finds it by that attribute

    const dead = info?.dead ? ' dead' : ''; // razed settlement → drained + struck-through style
    const medal = info?.rank ? `<img src="assets/img/podium/${info.rank}.png" />` : ''; // top-3 of the composite settlement weight
    const size = info?.size ? `<span class="tag-badge">${info.size}</span>` : ''; // Civ-style population-tier badge (1 foyer … 7 métropole).
    const ring = PaletteHelpers.realmRing(info?.kingdom); // its crown's emblem tint, framing the plate as it frames that crown's own tag
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const style = `--tag-color: ${PaletteHelpers.realmHue(info?.kingdom)}${ring ? `; --tag-ring: ${ring}` : ''}`; // omitted, never empty — empty kills the fallback

    return `<span class="ant-tag entity-tag${dead}" style="${style}">${crown}<span class="entity-name">${name}</span>${medal}${size}${species}</span>`;
  }

  // A realm plate: banner, name, podium medal, city count, species glyph — the heraldry comes first, as it does in WB's own kingdom list.
  private static _renderKingdom(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = KINGDOM_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const banner = `<canvas class="banner" data-kingdom="${id}" height="0" width="0"></canvas>`; // `KingdomSpriteHelpers.paintAll` composes it once rendered

    const cities = info?.cities ? `<span class="tag-badge">${info.cities}</span>` : ''; // city-count badge, mirrors the city-tag size medallion
    const dead = info?.dead ? ' dead' : ''; // destroyed kingdom → drained + struck-through style
    const label = `<span class="entity-name">${name}</span>`;
    const medal = info?.rank ? `<img src="assets/img/podium/${info.rank}.png" />` : ''; // top-3 of the composite power score, as the city's is
    const ring = info?.banner_icon_color ? `; --tag-ring: ${info.banner_icon_color}` : ''; // the emblem tint framing the plate, as on its cities' own tags
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const style = `--tag-color: ${info?.color ?? ''}${ring}`;

    return `<span class="ant-tag entity-tag${dead}" style="${style}">${banner}${label}${medal}${cities}${species}</span>`;
  }

  // A subject plate: the actor as WB draws them, name, sex, then their charge where the other plates put a species glyph — the portrait already shows it.
  private static _renderPerson(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = PERSON_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;
    if (!info) return name;

    const portrait = `<canvas class="portrait" data-person="${id}" height="0" width="0"></canvas>`; // `ActorSpriteHelpers.paintAll` fills it once rendered

    const color = PaletteHelpers.realmHue(info.kingdom); // their realm's own name hue — a subject reads as belonging to that crown
    const dead = info.dead ? ' dead' : ''; // fallen actor → drained + struck-through style
    const label = `<span class="entity-name">${name}</span>`;
    const profession = info.profession ? `<img src="assets/img/professions/${info.profession}.png" />` : '';
    const level = info.level ? `<span class="tag-badge">${info.level}</span>` : ''; // only once earned — Python omits the level-1 crowd
    const sex = info.sex ? `<img src="assets/img/sex/${info.sex}.png" />` : ''; // Folded pre-history founders carry no actor data — no sex to show.

    const badge = info.dead ? '<img src="assets/img/world/deaths.png" />' : profession;
    const hue = PaletteHelpers.realmRing(info.kingdom); // their crown's emblem tint, framing the plate exactly as it frames the crown's own tag
    const style = `--tag-color: ${color}${hue ? `; --tag-ring: ${hue}` : ''}`;

    return `<span class="ant-tag entity-tag${dead}" style="${style}">${portrait}${label}${level}${sex}${badge}</span>`;
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

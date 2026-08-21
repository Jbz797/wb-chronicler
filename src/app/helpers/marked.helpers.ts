import { marked, TokenizerAndRendererExtension, Tokens } from 'marked';
import { gfmHeadingId } from 'marked-gfm-heading-id';

import {
  BOOK_REGISTRY, CITY_REGISTRY, CLAN_REGISTRY, CULTURE_REGISTRY, FAMILY_REGISTRY, INLINE_MARKER, KINGDOM_REGISTRY, LANGUAGE_REGISTRY, PERSON_REGISTRY,
  SPECIES_COLORS, SUBSPECIES_REGISTRY,
} from '../constants';
import { IconKind, IconToken, InlineMarker, ParserThis } from '../interfaces';

import { PaletteHelpers } from './palette.helpers';
import { SubspeciesSpriteHelpers } from './sprites/subspecies-sprite.helpers';

export class MarkedHelpers {

  // The markers a registry resolves, hence an id that is a number — `[r]`/`[s]` name their asset instead.
  private static readonly _numericIdMarkers = new Set<InlineMarker>([
    INLINE_MARKER.Book,
    INLINE_MARKER.City,
    INLINE_MARKER.Clan,
    INLINE_MARKER.Culture,
    INLINE_MARKER.Family,
    INLINE_MARKER.Kingdom,
    INLINE_MARKER.Language,
    INLINE_MARKER.Person,
    INLINE_MARKER.Subspecies,
  ]);

  // Inline icon codes — each one a `[<letter> <id> <name>]` marker handled by its own renderer.
  public static configure(): void {
    marked.use(gfmHeadingId());
    marked.use({
      extensions: [
        this._extension(INLINE_MARKER.Book, 'books', false, this._renderBook), // `[b <id> <title>]` = book (its board + title in its genre's hue + readings).
        this._extension(INLINE_MARKER.City, 'cities', false, this._renderCity), // `[c <id> <name>]` = city (glyph + name, in its kingdom's palette).
        this._extension(INLINE_MARKER.Clan, 'clans', false, this._renderClan), // `[l <id> <name>]` = clan (name in its own hue + headcount).
        this._extension(INLINE_MARKER.Culture, 'cultures', false, this._renderCulture), // `[t <id> <name>]` = culture (emblem + name + followers).
        this._extension(INLINE_MARKER.Family, 'families', false, this._renderFamily), // `[f <id> <name>]` = family (WB's picture frame + name).
        this._extension(INLINE_MARKER.Kingdom, 'kingdoms', false, this._renderKingdom), // `[k <id> <name>]` = kingdom (colored name + banner icon).
        this._extension(INLINE_MARKER.Language, 'languages', false, this._renderLanguage), // `[a <id> <name>]` = language (emblem + name + speakers).
        this._extension(INLINE_MARKER.Person, 'persons', false, this._renderPerson), // `[p <id> <name>]` = person (portrait + name + sex icon + charge).
        this._extension(INLINE_MARKER.Resource, 'resources', true, this._renderResource), // `[r <id> <text>?]` = resource (icon + optional text, never colored).
        this._extension(INLINE_MARKER.Species, 'species', true, this._renderSpecies), // `[s <id> <text>?]` = species (icon + optional colored text).
        this._extension(INLINE_MARKER.Subspecies, 'subspecies', false, this._renderSubspecies), // `[u <id> <name>]` = subspecies (name in its own hue + bearers).
      ],
    });
  }

  // Build a marked inline extension for a `[<letter> <id> <name>]` marker — the shape every kind shares.
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

  // Inline-code regex: numeric id for the four registered entities (else `[_a-z]+`), name optional per caller.
  private static readonly _iconPattern = (letter: InlineMarker, { isNameOptional }: { isNameOptional: boolean }): RegExp => {
    const id = this._numericIdMarkers.has(letter) ? String.raw`\d+` : '[_a-z]+';
    const name = isNameOptional ? String.raw`(?: ([^\n\]]+))?` : String.raw` ([^\n\]]+)`;
    return new RegExp(String.raw`^\[${letter} (${id})${name}]`);
  };

  // A book plate: its own board, the title in its genre's hue, the readings badged — a volume answers to no crown and no stock, so it wears neither palette nor pip.
  private static _renderBook(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = BOOK_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const board = `<canvas class="board" data-book="${id}" height="0" width="0"></canvas>`; // `BookSpriteHelpers.paintAll` composes it once rendered

    const dead = info?.dead ? ' dead' : ''; // burnt since this chapter → drained + struck-through
    const reads = info?.reads ? `<span class="tag-badge">${info.reads}</span>` : ''; // times opened, dropped while nobody has
    const label = `<span class="entity-name">${name}</span>`;

    return `<span class="ant-tag entity-tag book-tag${dead}" style="--tag-color: ${info?.color}">${board}${label}${reads}</span>`;
  }

  // A settlement plate: WB's own slab as the ground, name, podium medal, size medallion, species glyph — the gold studs alone marking a seat.
  private static _renderCity(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = CITY_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const isCapital = info?.plate === 'capital'; // the gold-studded slab, which is what tells a seat from the rest now that no crown does
    const dead = info?.dead ? ' dead' : ''; // razed settlement → drained + struck-through style
    const medal = info?.rank ? `<img src="assets/img/podium/${info.rank}.png" />` : ''; // top-3 of the composite settlement weight
    const size = info?.size ? `<span class="tag-badge">${info.size}</span>` : ''; // Civ-style population-tier badge (1 foyer … 7 métropole).
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const style = `--tag-color: ${PaletteHelpers.realmText(info?.kingdom)}; --tag-plate: url('assets/img/nameplates/${isCapital ? 'capital' : 'city'}.png')`;

    const classes = `ant-tag entity-tag city-tag${isCapital ? ' capital' : ''}${dead}`;

    return `<span class="${classes}" style="${style}"><span class="entity-name">${name}</span>${medal}${size}${species}</span>`;
  }

  // A clan plate: its own hue, name and living headcount. Sworn rather than granted, so it borrows no crown's palette and hangs no banner.
  private static _renderClan(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = CLAN_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const banner = `<canvas class="banner" data-clan="${id}" height="0" width="0"></canvas>`; // `KingdomSpriteHelpers.paintAll` composes it once rendered

    const dead = info?.dead ? ' dead' : ''; // clan disbanded since this chapter → drained + struck-through
    const members = info?.members ? `<span class="tag-badge">${info.members}</span>` : ''; // living headcount, as the lineage plate badges its own
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const label = `<span class="entity-name">${name}</span>`;

    return `<span class="ant-tag entity-tag clan-tag${dead}" style="--tag-color: ${info?.color}">${banner}${label}${members}${species}</span>`;
  }

  // A culture plate: WB's own stone frame, its emblem, its hue and the living it is caught by. Raised into rather than granted, so it borrows no crown's palette.
  private static _renderCulture(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = CULTURE_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const emblem = `<canvas class="banner" data-culture="${id}" height="0" width="0"></canvas>`; // `CultureSpriteHelpers.paintAll` composes it once rendered

    const dead = info?.dead ? ' dead' : ''; // custom lost with its last follower → drained + struck-through
    const medal = info?.rank ? `<img src="assets/img/podium/${info.rank}.png" />` : ''; // top-3 by followers, the one axis a culture is ranked on
    const members = info?.members ? `<span class="tag-badge">${info.members}</span>` : ''; // living followers, as the clan plate badges its own
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const label = `<span class="entity-name">${name}</span>`;

    return `<span class="ant-tag entity-tag culture-tag${dead}" style="--tag-color: ${info?.color}">${emblem}${label}${medal}${members}${species}</span>`;
  }

  // A lineage wears no crown's hue, so its tag is the frame alone on a plain ground — nothing to resolve but the sprite.
  private static _renderFamily(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = FAMILY_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const dead = info?.dead ? ' dead' : ''; // lineage died out since this chapter → drained + struck-through
    const framed = info?.frame === undefined ? '' : ' framed';
    const n = info?.frame === undefined ? null : String(info.frame).padStart(2, '0');

    // Two sprites off the same number: the rails, then the corner volutes those rails are too thin to hold — the pair `family-tag.component.ts` binds.
    const border = n === null ? '' : `--tag-border: url(assets/img/families/frame_${n}.png); --tag-corner: url(assets/img/families/corner_${n}.png); `;
    const members = info?.members ? `<span class="tag-badge">${info.members}</span>` : ''; // living headcount, as the city plate badges its citizens
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const style = `${border}--tag-fill: ${info?.bg_color}; --tag-ink: ${PaletteHelpers.readableOn(info?.bg_color)}`;

    return `<span class="ant-tag family-tag${framed}${dead}" style="${style}"><span class="entity-name">${name}</span>${members}${species}</span>`;
  }

  private static _renderKingdom(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = KINGDOM_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const banner = `<canvas class="banner" data-kingdom="${id}" height="0" width="0"></canvas>`; // `KingdomSpriteHelpers.paintAll` composes it once rendered

    const cities = info?.cities ? `<span class="tag-badge">${info.cities}</span>` : ''; // city-count badge, mirrors the city-tag size medallion
    const dead = info?.dead ? ' dead' : ''; // destroyed kingdom → drained + struck-through style
    const label = `<span class="entity-name">${name}</span>`;
    const medal = info?.rank ? `<img src="assets/img/podium/${info.rank}.png" />` : ''; // top-3 of the composite power score, as the city's is
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const style = `--tag-color: ${PaletteHelpers.realmText(Number(id))}`; // the plate itself frames it now, where an emblem-tinted ring used to

    return `<span class="ant-tag entity-tag kingdom-tag${dead}" style="${style}">${banner}${label}${medal}${cities}${species}</span>`;
  }

  // A language plate: WB's own parchment, the script inked on it, its hue and the living who answer in it. Caught by ear, so it borrows no crown's palette.
  private static _renderLanguage(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = LANGUAGE_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const emblem = `<canvas class="banner" data-language="${id}" height="0" width="0"></canvas>`; // `LanguageSpriteHelpers.paintAll` composes it once rendered

    const dead = info?.dead ? ' dead' : ''; // tongue lost with its last speaker → drained + struck-through
    const medal = info?.rank ? `<img src="assets/img/podium/${info.rank}.png" />` : ''; // top-3 by speakers, the one axis a language is ranked on
    const speakers = info?.speakers ? `<span class="tag-badge">${info.speakers}</span>` : ''; // the living who answer in it, as the culture plate badges its own
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const label = `<span class="entity-name">${name}</span>`;

    return `<span class="ant-tag entity-tag language-tag${dead}" style="--tag-color: ${info?.color}">${emblem}${label}${medal}${speakers}${species}</span>`;
  }

  // A subject plate: the actor as WB draws them, name, sex, then their charge where the other plates put a species glyph — the portrait already shows it.
  private static _renderPerson(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = PERSON_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;
    if (!info) return name;

    const portrait = `<canvas class="portrait" data-person="${id}" height="0" width="0"></canvas>`; // `ActorSpriteHelpers.paintAll` fills it once rendered

    const color = PaletteHelpers.realmText(info.kingdom); // their realm's own name hue — a subject reads as belonging to that crown
    const dead = info.dead ? ' dead' : ''; // fallen actor → drained + struck-through style
    const label = `<span class="entity-name">${name}</span>`;
    const job = info.job ? `<img src="assets/img/professions/${info.job}.png" />` : ''; // the dead keep theirs — the drained plate already says they are gone
    const level = info.level ? `<span class="tag-badge">${info.level}</span>` : ''; // only once earned — Python omits the level-1 crowd
    const sex = info.sex ? `<img src="assets/img/sex/${info.sex}.png" />` : ''; // Folded pre-history founders carry no actor data — no sex to show.

    const hue = PaletteHelpers.realmRing(info.kingdom); // their crown's emblem tint, framing the plate exactly as it frames the crown's own tag
    const style = `--tag-color: ${color}${hue ? `; --tag-ring: ${hue}` : ''}`;

    return `<span class="ant-tag entity-tag${dead}" style="${style}">${portrait}${label}${level}${sex}${job}</span>`;
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

  // A biology is written on stone: the plate takes the slab whole, hangs the dyed bookmark on it, and keeps its hue for the name, the bearers and the pip.
  private static _renderSubspecies(this: ParserThis, token: Tokens.Generic): string {
    const { id, tokens: children } = token as IconToken;
    const info = SUBSPECIES_REGISTRY[id];
    const name = children?.length ? this.parser.parseInline(children) : id;

    const bookmark = `<canvas class="bookmark" data-subspecies="${id}" height="0" width="0"></canvas>`; // `SubspeciesSpriteHelpers.paintAll` dyes it once rendered

    const dead = info?.dead ? ' dead' : ''; // biology extinct since this chapter → drained + struck-through
    const members = info?.members ? `<span class="tag-badge">${info.members}</span>` : ''; // living bearers, as the clan plate badges its sworn
    const species = info?.species ? `<img src="assets/img/species/${info.species}.png" />` : '';
    const label = `<span class="entity-name">${name}</span>`;

    const style = `--tag-color: ${info?.color}; --tag-slab: ${SubspeciesSpriteHelpers.slab(info?.banner_bg)}`;
    return `<span class="ant-tag entity-tag subspecies-tag${dead}" style="${style}">${bookmark}${label}${members}${species}</span>`;
  }

}

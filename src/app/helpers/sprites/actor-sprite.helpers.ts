import { ActorAtlas, ActorPose, ActorRect, ActorSheets, PersonInfo } from '../../interfaces';
import { PaletteHelpers } from '../palette.helpers';

import { SpriteHelpers } from './sprite.helpers';

// Composes an actor the way WorldBox does — body, weapon, then head — over the plumbing in `SpriteHelpers`. Feeds every `[p]` plate, panel and prose alike.
export class ActorSpriteHelpers {

  private static readonly _atlas = fetch('assets/img/actors/actors.json').then(r => r.json() as Promise<ActorAtlas>);
  private static readonly _bodySheets: Record<string, string> = { army_captain: 'warrior_1', king: 'king', leader: 'leader', warrior: 'warrior_1' };
  private static readonly _darkerFactors = [1, 0.9, 0.8, 0.7]; // WB `loadPhenotype`: the four greens are one skin colour at four `makeDarkerColor` steps
  private static readonly _lightPlaceholder: [string, string] = ['255,216,0', '0,0,0'];
  private static readonly _phenotypeGreens = ['184,255,150', '0,255,0', '0,175,0', '74,131,31']; // WB `color_phenotype_green_0..3` → the skin shades
  private static readonly _scale = 3; // every body (6-16px) then clears the 22px cap `canvas.portrait` imposes, so each one fills it
  private static readonly _sprites = new Map<string, Promise<HTMLCanvasElement | null>>();

  // The only one of the three drawn scaled — a body is 6-16px, well under the 22px cap `canvas.portrait` imposes.
  public static async paint(canvas: HTMLCanvasElement, actor: PersonInfo): Promise<void> {
    SpriteHelpers.blit(canvas, await this._compose(actor), this._scale);
  }

  public static paintAll(root: ParentNode, persons: Record<string, PersonInfo | undefined>): void {
    SpriteHelpers.paintAll(root, 'person', persons, (canvas, actor) => this.paint(canvas, actor));
  }

  // Pivot on pivot vertically — it seats a head in its collar, not a pixel above. Centred horizontally: WB's x-pivot is a mirror axis, not a placement point.
  private static async _blit(context: CanvasRenderingContext2D, url: string, source: ActorRect | undefined, anchor: ActorRect): Promise<void> {
    if (!source) return;
    const [sx, sy, sw, sh, sourcePivot] = source;
    const [ax, ay, aw, , anchorPivot] = anchor;
    const dx = Math.round(ax + (aw - sw) / 2);
    const dy = Math.round(ay + anchorPivot - sourcePivot);
    context.drawImage(await SpriteHelpers.load(url), sx, sy, sw, sh, dx, dy, sw, sh);
  }

  // Body → weapon → head, each blitted from its atlas rect, then the whole recoloured in one pass. `null` when the species ships no sheet we can draw.
  private static async _build(actor: PersonInfo, hue: string): Promise<HTMLCanvasElement | null> {
    const sheets = await this._atlas;
    const species = sheets.species[actor.asset_id];
    const sex = actor.sex === 'female' ? 'female' : 'male';

    // Rank sheet first, then the plain civilian of that sex, then the lone `main` a flat species (most animals) ships instead.
    const body = [this._bodySheets[actor.profession ?? ''], `${sex}_1`, 'main'].find(name => name && species?.bodies[name]);
    const pose: ActorPose | undefined = body ? species?.bodies[body] : undefined;

    if (!species || !pose) return null;

    const [bx, by, bw, bh] = pose.body;
    const cut = document.createElement('canvas');
    cut.height = bh;
    cut.width = bw;
    const context = cut.getContext('2d');
    if (!context) return null;

    context.drawImage(await SpriteHelpers.load(`assets/img/actors/${actor.asset_id}/${body ?? ''}.png`), bx, by, bw, bh, 0, 0, bw, bh);

    if (pose.item && actor.weapon) {
      const sprite = `w_${actor.weapon}`;
      await this._blit(context, `assets/img/actors/weapons/${sprite}.png`, sheets.weapons[sprite], pose.item);
    }

    if (pose.head) await this._head(context, actor, species, sex, pose.head);

    SpriteHelpers.repaint(context, bw, bh, this._swaps(sheets, actor, hue)); // once, assembled — every part still wears its placeholders until here
    return cut;
  }

  // Keyed on the whole visual identity, realm hue included — two subjects alike to the pixel share one sprite, however many tags and panels echo them.
  private static async _compose(actor: PersonInfo): Promise<HTMLCanvasElement | null> {
    const hue = PaletteHelpers.realmHue(actor.kingdom);
    const key = [
      actor.asset_id,
      actor.sex,
      actor.profession,
      actor.head,
      actor.special_head,
      actor.phenotype_index,
      actor.phenotype_shade,
      actor.weapon,
      hue,
    ].join(',');
    return SpriteHelpers.compose(this._sprites, key, () => this._build(actor, hue));
  }

  // WB `Actor.checkSpriteHead`: a helmet, a crown or the wise's white hair replace the head, never overlay it — Python picks which, we only fetch the sheet.
  private static async _head(
    context: CanvasRenderingContext2D,
    actor: PersonInfo,
    species: ActorSheets,
    sex: string,
    anchor: ActorRect,
  ): Promise<void> {
    const special = actor.special_head === 'head_old' ? `head_old_${sex}` : actor.special_head;
    const rect = special ? species.hats[special] : undefined;
    if (rect) {
      await this._blit(context, `assets/img/actors/${actor.asset_id}/${special}.png`, rect, anchor);
      return;
    }

    const sheet = [`heads_${sex}`, 'heads'].find(name => species.heads[name]); // the sexless `heads` sheet is what skeletons and the like ship
    const variants = sheet ? species.heads[sheet] ?? [] : [];
    const head = variants[(actor.head ?? 0) % Math.max(1, variants.length)];
    if (head) await this._blit(context, `assets/img/actors/${actor.asset_id}/${sheet}.png`, head, anchor);
  }

  // The realm ramp every WB sprite shares, extended with what only an actor carries: four greens for the four shades of their skin.
  private static _swaps(sheets: ActorAtlas, actor: PersonInfo, hue: string): Map<string, string> {
    const swaps = SpriteHelpers.realmRamp(hue);
    swaps.set(...this._lightPlaceholder); // WB `drawPixelsAll` blacks `arr_pixels_light` unconditionally — the 37 px of `#FFD800` on the special heads.
    const [from, to] = sheets.phenotypes[String(actor.phenotype_index ?? 0)] ?? sheets.phenotypes['1'] ?? [];
    if (from && to) {
      const skin = SpriteHelpers.blend(SpriteHelpers.hexRgb(from), SpriteHelpers.hexRgb(to), 1 - (actor.phenotype_shade ?? 0) / 3); // `PhenotypeAsset.colors[shade]`
      // Floored, not rounded — `makeDarkerColor` is a multiply, and Unity truncates on the way back to a byte, exactly as `blend` and `tint` do.
      this._phenotypeGreens.forEach((key, step) => swaps.set(key, skin.map(c => Math.floor(c * (this._darkerFactors[step] ?? 1))).join(',')));
    }

    return swaps;
  }

}

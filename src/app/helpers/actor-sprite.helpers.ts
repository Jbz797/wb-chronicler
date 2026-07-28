import { ActorAtlas, ActorPose, ActorRect, ActorSheets, PersonInfo } from '../interfaces';

import { PaletteHelpers } from './palette.helpers';
import { SpriteHelpers } from './sprite.helpers';

// Composes an actor the way WorldBox does — body, weapon, then head — over the plumbing in `SpriteHelpers`. Driven by `<app-actor-portrait>` and the prose tags.
export class ActorSpriteHelpers {

  private static readonly _atlas = fetch('assets/img/actors/actors.json').then(r => r.json() as Promise<ActorAtlas>);
  private static readonly _bodySheets: Record<string, string> = { army_captain: 'warrior_1', king: 'king', leader: 'leader', warrior: 'warrior_1' };
  private static readonly _darkerFactors = [1, 0.9, 0.8, 0.7]; // WB `loadPhenotype`: the four greens are one skin colour at four `makeDarkerColor` steps
  private static readonly _phenotypeGreens = ['184,255,150', '0,255,0', '0,175,0', '74,131,31']; // WB `color_phenotype_green_0..3` → the skin shades
  private static readonly _scale = 3; // every body (6-16px) then clears the 22px cap `canvas.portrait` imposes, so each one fills it
  private static readonly _sprites = new Map<string, Promise<HTMLCanvasElement | null>>();

  // Scales the composed sprite onto the caller's canvas, at whole pixels so the art stays crisp.
  public static async paint(canvas: HTMLCanvasElement, actor: PersonInfo): Promise<void> {
    const sprite = await this._compose(actor);
    const context = canvas.getContext('2d');
    if (!sprite || !context) {
      canvas.height = 0; // a species we hold no sheet for must take no room at all, not the 300×150 a bare canvas defaults to
      canvas.width = 0;
      return;
    }

    canvas.height = sprite.height * this._scale; // resizing resets the context, so smoothing goes off after it, not before
    canvas.width = sprite.width * this._scale;
    context.imageSmoothingEnabled = false;
    context.drawImage(sprite, 0, 0, sprite.width, sprite.height, 0, 0, canvas.width, canvas.height);
  }

  // Paints every `<canvas data-person>` marked left in a rendered chapter. Unknown ids and species collapse to nothing rather than a blank box.
  public static paintAll(root: ParentNode, persons: Record<string, PersonInfo | undefined>): void {
    for (const canvas of root.querySelectorAll<HTMLCanvasElement>('canvas[data-person]')) {
      const actor = persons[canvas.dataset.person ?? ''];
      if (actor) this.paint(canvas, actor).catch(() => {}); // a missing sheet just leaves the canvas collapsed
    }
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

  // Keyed on the whole visual identity, realm hue included: the two `[p 7]` tags of one chapter, and every panel echoing them, compose once between them.
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
    const cached = this._sprites.get(key);
    if (cached) return cached;
    const pending = this._build(actor, hue);
    this._sprites.set(key, pending);
    return pending;
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
    const [from, to] = sheets.phenotypes[String(actor.phenotype_index ?? 0)] ?? sheets.phenotypes['1'] ?? [];
    if (from && to) {
      const skin = SpriteHelpers.blend(SpriteHelpers.hexRgb(from), SpriteHelpers.hexRgb(to), 1 - (actor.phenotype_shade ?? 0) / 3); // `PhenotypeAsset.colors[shade]`
      this._phenotypeGreens.forEach((key, step) => swaps.set(key, skin.map(c => Math.round(c * (this._darkerFactors[step] ?? 1))).join(',')));
    }

    return swaps;
  }

}

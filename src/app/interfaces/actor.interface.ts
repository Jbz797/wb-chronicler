import { ActorRect } from './types';

// `phenotypes` maps WB's 1-based phenotype index to its `[shades_from, shades_to]` hex pair — the four skin shades are Lerped between them.
export interface ActorAtlas { phenotypes: Record<string, [string, string]>; species: Record<string, ActorSheets>; weapons: Record<string, ActorRect> }

// The `walk_0` body rect plus, in body-relative coords, the anchors WB ships alongside it. Flat species (a lone `main` sheet) carry neither.
export interface ActorPose { body: ActorRect; head?: ActorRect; item?: ActorRect }

// `bodies` is keyed by sheet (`main`, `male_1`, `king`…), `hats` by the crown/helmet overlay WB draws at the head anchor, `heads` by sheet then variant.
export interface ActorSheets { bodies: Record<string, ActorPose>; hats: Record<string, ActorRect>; heads: Record<string, ActorRect[]> }

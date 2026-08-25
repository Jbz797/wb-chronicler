import { EntityReference, HullCount } from '../entity.interface';
import { LeaderKind } from '../types';

// A « Records » row ready for the UI: a Leader tagged with its category key + whether it changed since the previous chapter.
export interface LeaderRow extends Omit<Leader, 'name' | 'value'> { isNew: boolean; key: LeaderKind; name: string }

// The world panel's four blocks: live snapshot, cumulative counters, « Records » leaders, and metadata.
export interface World {
  boats: HullCount;
  cumulative: WorldCumulative;
  leaders?: Partial<Record<LeaderKind, Leader>>;
  metadata: WorldMetadata;
  plots?: WorldPlot[]; // absent where nobody schemes — Python omits the empty list
  snapshot: WorldSnapshot;
}

// The world's own identity, chronicler-authored in `history/world.json` — the name alone reaches a panel, the sentence beside it framing the chronicle.
export interface WorldInfo { name: string }

// Every scheme afoot, its schemer named — WB hangs one on a single actor, and `actor/info.py <id> plot` tells the chronicler the rest.
export interface WorldPlot { actor: EntityReference; type: { id: string; name: string } }

// Per-cause death counts since world start — Python omits 0-counts, so UI must treat absent keys as 0.
interface DeathBreakdown {
  acid?: number;
  divine?: number;
  drowning?: number;
  eaten?: number;
  explosion?: number;
  fire?: number;
  gravity?: number;
  hunger?: number;
  infection?: number;
  old_age?: number;
  other?: number;
  plague?: number;
  poison?: number;
  tumor?: number;
  water?: number;
  weapon?: number;
}

// The winner of a « Records » category: `dominant_species` carries `asset_id` (its icon); every other kind is a `{id, name}` ref the UI resolves via its registry.
interface Leader { asset_id?: string; id?: number; name?: string; value?: number }

// Since-world-start counters the UI diffs per chapter; Python omits 0-counts, so an absent key means 0.
interface WorldCumulative {
  books_burnt?: number;
  books_read?: number;
  cities_conquered?: number;
  cities_rebelled?: number;
  deaths?: DeathBreakdown;
  evolutions?: number;
  metamorphosis?: number;
  plots_succeeded?: number;
}

// The world's current age id and its `world_time` clock — what the chapter header reads.
interface WorldMetadata { age_id: string; world_time: number }

// Live counts of every world entity at this chapter (population, buildings, cultures…); `infected`/`sick` are omitted when 0.
interface WorldSnapshot {
  alliances: number;
  armies: number;
  books: number;
  buildings: number;
  cities: number;
  clans: number;
  cultures: number;
  families: number;
  frozen_tiles: number;
  houses: number;
  infected?: number;
  kingdoms: number;
  languages: number;
  population: number;
  religions: number;
  sick?: number;
  subspecies: number;
  trees: number;
  vegetation: number;
  wars: number;
  wild_creatures: number;
}

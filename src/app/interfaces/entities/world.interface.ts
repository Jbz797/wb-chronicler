import { EntityReference, HullCount } from '../entity.interface';
import { LeaderGroup, LeaderMeasure } from '../types';

// A « Records » table: the group it reads, its heading, and the records it names, in order.
export interface LeaderGroupConfig { group: LeaderGroup; label: string; measures: LeaderMeasure[] }

// A « Records » row ready for the UI: a Leader tagged with its group + whether it changed since the previous chapter.
export interface LeaderRow extends Omit<Leader, 'name'> { group: LeaderGroup; isNew: boolean; name: string }

// A snapshot row while it is still being built — `hideIfZero` drops the idle ones on the way out, `icon` names the sprite where the key is not what it draws.
export interface SnapshotRow { delta: number | undefined; hideIfZero: boolean | undefined; icon: string | undefined; key: string; label: string; value: number }

// The world panel's four blocks: live snapshot, cumulative counters, « Records » leaders, and metadata.
export interface World {
  boats: HullCount;
  cumulative?: WorldCumulative; // absent on a bare world — Python omits the block when every counter is 0
  leaders?: Partial<Record<LeaderGroup, Partial<Record<LeaderMeasure, Leader>>>>;
  metadata: WorldMetadata;
  plots?: WorldPlot[]; // absent where nobody schemes — Python omits the empty list
  snapshot: WorldSnapshot;
}

// `history/world.json` mirrors the identity the save carries, name and description alike — WorldBox shows the sentence in its own world list, no panel here does.
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

// The first holder of a « Records » place: `species` carries `asset_id` (its icon); every other group is a `{id, name}` ref the UI resolves via its registry.
interface Leader { asset_id?: string; id?: number; name?: string }

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

// The world's current age id — the panel title's age. Its `world_time` clock reaches the nav through `index.json`.
interface WorldMetadata { age_id: string }

// Live counts of every world entity at this chapter (thinking souls, buildings, cultures…); `infected`/`sick` are omitted when 0.
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
  religions: number;
  sapient_population: number;
  sick?: number;
  subspecies: number;
  trees: number;
  vegetation: number;
  wars: number;
  wild_creatures: number;
}

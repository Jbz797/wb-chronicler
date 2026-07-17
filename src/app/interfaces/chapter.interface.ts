import { Page } from './page.interface';
import { RarityCounts } from './stats.interface';
import { LeaderKind, LifeStage } from './types';

// One chronicle chapter: a nav Page plus its parsed chapter.json `meta` and preview image.
export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

// A parsed chapter.json: the three overview panels (favorite/kingdom/world) plus the age label and prose tags.
export interface ChapterMeta {
  age_label: string;
  favorite: Favorite | null;
  kingdom: Kingdom | null;
  tags: string[];
  world: World;
}

// `allies` is absent, not empty, if the kingdom is the alliance's last member. `population`/`renown` sum its members. `motto` is chronicler-only (omitted from TS).
export interface KingdomAlliance {
  allies?: KingdomReference[];
  breakdown: PopulationBreakdown;
  name: string;
  population: number;
  ranks?: { population?: number; renown?: number };
  renown: number;
}

// This kingdom's diplomatic tie to one other — ally/enemy/neutral, with the net opinion score driving the tag colour.
export interface KingdomRelation {
  kingdom: KingdomReference;
  opinion: { total: number };
  status: 'ally' | 'enemy' | 'neutral';
}

// `allies` is absent when a kingdom fights alone, both `*_alliance` when no alliance backs that side, `war_type` when WB never set one — `emit` strips them all.
export interface KingdomWar {
  allies?: KingdomReference[];
  attacker_alliance?: KingdomReference;
  cities: SideStats;
  deaths: SideStats;
  defender_alliance?: KingdomReference;
  duration_years: number;
  id: number;
  name: string;
  opponents: KingdomReference[];
  populations: SideStats;
  renown_at_stake: number;
  side: 'attacker' | 'defender';
  started_by: { kingdom: KingdomReference };
  war_type?: 'conquest' | 'inspire' | 'rebellion' | 'spite' | 'whisper';
  warriors: SideStats;
}

// A « Records » row ready for the UI: a Leader tagged with its category key + whether it changed since the previous chapter.
export interface LeaderRow extends Omit<Leader, 'value'> { isNew: boolean; key: LeaderKind }

// A favorite's lover or best friend — the minimal actor fields the companion card renders.
interface Companion {
  age: number;
  health_max: number;
  id: number;
  level: number;
  money: number;
  name: string;
  renown: number;
  sex: 'female' | 'male';
}

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

// Absent, never null: `emit` strips `None`/`[]`/`{}` — no lover, no plot, an empty bag or no top-3 rank means no key. `descriptor` is authored by the chronicler.
interface Favorite {
  best_friend?: Companion;
  descriptor: string;
  inventory?: Record<string, number>;
  lover?: Companion;
  metadata: FavoriteMetadata;
  plot?: Plot;
  ranks_in_species?: FavoriteRanks;
  stats: FavoriteStats;
  traits: RarityCounts;
}

// The favorite's identity and civic standing (species, kingdom, roles…); optional fields are dropped by Python when the actor has none.
interface FavoriteMetadata {
  age: number;
  asset_id: string;
  kingdom?: KingdomReference;
  life_stage: LifeStage;
  name: string;
  personality?: string;
  profession: string;
  roles?: string[];
  sex: 'female' | 'male';
  tenure_years?: number;
}

// The favorite's rank (1-3) per stat among its species peers — all optional: a stat is absent when the favorite isn't on its podium.
interface FavoriteRanks {
  age?: number;
  armor?: number;
  attack_speed?: number;
  birth_rate?: number;
  children?: number;
  critical_chance?: number;
  damage?: number;
  diplomacy?: number;
  equipment_power?: number;
  health_max?: number;
  intelligence?: number;
  kills?: number;
  level?: number;
  lifespan?: number;
  loot?: number;
  mana_max?: number;
  money?: number;
  renown?: number;
  speed?: number;
  stamina_max?: number;
  stewardship?: number;
  warfare?: number;
}

// The favorite's raw combat / social / vital stats — WB runtime values, always present.
interface FavoriteStats {
  armor: number;
  attack_speed: number;
  birth_rate: number;
  children: number;
  critical_chance: number;
  damage: number;
  diplomacy: number;
  equipment_power: number;
  happiness: number;
  health: number;
  health_max: number;
  intelligence: number;
  kills: number;
  level: number;
  lifespan: number;
  loot: number;
  mana: number;
  mana_max: number;
  max_children: number;
  money: number;
  nutrition: number;
  renown: number;
  speed: number;
  stamina: number;
  stamina_max: number;
  stewardship: number;
  warfare: number;
}

// Absent, not empty: Python's `emit` strips `None`/`[]`/`{}`, so no podium, no neighbour or no ongoing war means no key at all.
interface Kingdom {
  alliance?: KingdomAlliance;
  breakdown: PopulationBreakdown;
  metadata: KingdomMetadata;
  population: KingdomPopulation;
  ranks?: KingdomRanks;
  relations?: KingdomRelation[];
  wars?: KingdomWar[];
}

// The kingdom's own attributes (age, capital, king/heir/founder, resource stocks…) — as opposed to `population`, which aggregates its inhabitants.
interface KingdomMetadata {
  age: number;
  buildings: number;
  capital?: string;
  cities: number;
  deaths: number;
  food: number;
  founder?: { asset_id: string; dead: boolean; id: number; name: string; profession?: string; sex?: 'female' | 'male' };
  gold: number;
  goods: number;
  heir?: { asset_id: string; id: number; name: string; profession?: string; sex: 'female' | 'male' };
  houses: number;
  id: number;
  kills: number;
  king?: { asset_id: string; id: number; money: number; name: string; sex: 'female' | 'male' };
  name: string;
  renown: number;
  territory: number;
  wealth: number;
}

// Aggregates over the kingdom's inhabitants (demographics, wealth split, food/housing ratios) — distinct from the kingdom's own `metadata`.
interface KingdomPopulation {
  fed_pct: number;
  food_per_capita: number;
  housed_pct: number;
  immortals?: number;
  infected?: number;
  money: number;
  nobles: number;
  nobles_money: number;
  renown_total: number;
  sick?: number;
  subjects_money: number;
  total: number;
  warriors: number;
  wealth_per_capita: number;
}

// The kingdom's rank (1-3) per stat among all kingdoms — all optional: present only when the kingdom is on that stat's podium.
interface KingdomRanks {
  age?: number;
  buildings?: number;
  cities?: number;
  deaths?: number;
  fed_pct?: number;
  food?: number;
  food_per_capita?: number;
  gold?: number;
  goods?: number;
  housed_pct?: number;
  houses?: number;
  immortals?: number;
  infected?: number;
  kills?: number;
  king_money?: number;
  money?: number;
  nobles?: number;
  nobles_money?: number;
  population?: number;
  renown?: number;
  renown_total?: number;
  sick?: number;
  subjects_money?: number;
  territory?: number;
  warriors?: number;
  wealth?: number;
  wealth_per_capita?: number;
}

// A minimal id + name pointer to a kingdom, for tags and cross-links.
interface KingdomReference { id: number; name: string }

// The winner of a « Records » category; shape varies by kind (person carries asset_id/sex, the rest just id + name).
interface Leader { asset_id?: string; id?: number; name: string; profession?: string; sex?: 'female' | 'male'; value: number }

// The favorite's active scheme (WB `Plot`); `target_*` are absent when the plot has no such target.
interface Plot {
  name: string;
  progress: number;
  target_alliance?: string;
  target_kingdom?: string;
  type_id: string;
}

// Top-3 shares of a civ population per dimension (% of the whole). `species`/`subspecies` always ≥1 (`species` adds `asset_id`); the rest optional.
interface PopulationBreakdown {
  cultures?: { name: string; pct: number }[];
  languages?: { name: string; pct: number }[];
  religions?: { name: string; pct: number }[];
  species: { asset_id: string; name: string; pct: number }[];
  subspecies: { name: string; pct: number }[];
}

// A per-side tally (attackers vs defenders) — reused for a war's population, warriors, cities and deaths.
interface SideStats { attackers: number; defenders: number }

// The world panel's four blocks: live snapshot, cumulative counters, « Records » leaders, and metadata.
interface World {
  cumulative: WorldCumulative;
  leaders?: Partial<Record<LeaderKind, Leader>>;
  metadata: WorldMetadata;
  snapshot: WorldSnapshot;
}

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

// The world's current age id and its `world_time` clock (the two fields the chapter header needs).
interface WorldMetadata {
  age_id: string;
  world_time: number;
}

// Live counts of every world entity at this chapter (population, buildings, cultures…); `infected`/`sick` are omitted when 0.
interface WorldSnapshot {
  alliances: number;
  armies: number;
  books: number;
  buildings: number;
  cities: number;
  clans: number;
  cultures: number;
  equipment: number;
  families: number;
  frozen_tiles: number;
  houses: number;
  infected?: number;
  kingdoms: number;
  languages: number;
  plots_active: number;
  population: number;
  relations: number;
  religions: number;
  sick?: number;
  subspecies: number;
  trees: number;
  vegetation: number;
  wars: number;
  wild_creatures: number;
}

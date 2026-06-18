import { Page } from './page.interface';
import { RarityCounts } from './stats.interface';
import { LeaderKind } from './types';

export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

export interface ChapterMeta {
  age_label: string;
  favorite: Favorite | null;
  kingdom: Kingdom | null;
  tags: string[];
  world: World;
}

export interface KingdomRelation {
  kingdom: KingdomReference;
  opinion: { total: number };
  status: 'ally' | 'enemy' | 'neutral';
}

export interface KingdomWar {
  allies: KingdomReference[];
  attacker_alliance: KingdomReference | null;
  cities: SideStats;
  deaths: SideStats;
  defender_alliance: KingdomReference | null;
  duration_years: number;
  id: number;
  name: string;
  opponents: KingdomReference[];
  populations: SideStats;
  renown_at_stake: number;
  side: 'attacker' | 'defender';
  started_by: { kingdom: KingdomReference };
  war_type: 'conquest' | 'inspire' | 'rebellion' | 'spite' | 'whisper' | null;
  warriors: SideStats;
}

export interface LeaderRow extends Omit<Leader, 'value'> { isNew: boolean; key: LeaderKind }

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

interface Favorite {
  best_friend: Companion | null;
  descriptor: string;
  equipment: RarityCounts;
  inventory: Record<string, number>;
  lover: Companion | null;
  metadata: FavoriteMetadata;
  plot: Plot | null;
  ranks_in_species: FavoriteRanks;
  stats: FavoriteStats;
  traits: RarityCounts;
}

interface FavoriteMetadata {
  age: number;
  asset_id: string;
  kingdom: KingdomReference | null;
  name: string;
  personality: string | null;
  profession: string;
  roles: string[];
  sex: 'female' | 'male';
}

interface FavoriteRanks {
  age?: number;
  armor?: number;
  attack_speed?: number;
  birth_rate?: number;
  children?: number;
  critical_chance?: number;
  damage?: number;
  damage_range?: number;
  diplomacy?: number;
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

interface FavoriteStats {
  armor: number;
  attack_speed: number;
  birth_rate: number;
  children: number;
  critical_chance: number;
  damage: number;
  damage_range: number;
  diplomacy: number;
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

interface Kingdom {
  metadata: KingdomMetadata;
  ranks: KingdomRanks;
  relations: KingdomRelation[];
  wars: KingdomWar[];
}

interface KingdomMetadata {
  age: number;
  cities: number;
  id: number;
  name: string;
  population: number;
  renown: number;
  territory: number;
  warriors: number;
}

interface KingdomRanks {
  age?: number;
  cities?: number;
  population?: number;
  renown?: number;
  territory?: number;
  warriors?: number;
}

interface KingdomReference { id: number; name: string }

interface Leader { asset_id?: string; id?: number; name: string; sex?: 'female' | 'male'; value: number }

interface Plot {
  name: string;
  progress: number;
  target_alliance: string | null;
  target_kingdom: string | null;
  type_id: string;
}

interface SideStats { attackers: number; defenders: number }

interface World {
  cumulative: WorldCumulative;
  leaders?: Partial<Record<LeaderKind, Leader>>;
  metadata: WorldMetadata;
  snapshot: WorldSnapshot;
}

interface WorldCumulative {
  books_read?: number;
  cities_conquered?: number;
  cities_rebelled?: number;
  deaths: DeathBreakdown;
  plots_succeeded?: number;
}

interface WorldMetadata {
  age_id: string;
  world_time: number;
}

interface WorldSnapshot {
  alliances: number;
  armies: number;
  books: number;
  cities: number;
  clans: number;
  cultures: number;
  equipment: number;
  families: number;
  frozen_tiles: number;
  houses: number;
  infected: number;
  kingdoms: number;
  languages: number;
  plots_active: number;
  population: number;
  relations: number;
  religions: number;
  subspecies: number;
  trees: number;
  vegetation: number;
  wars: number;
  wild_creatures: number;
}

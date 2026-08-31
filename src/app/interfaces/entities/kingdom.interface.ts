import { EntityReference, EquipmentStock, HullCount, Leaders, PersonReference, PopulationBreakdown } from '../entity.interface';

// Absent, not empty: Python's `emit` strips `None`/`[]`/`{}`, so no podium, no neighbour or no ongoing war means no key at all.
export interface Kingdom {
  boats: HullCount;
  breakdown: PopulationBreakdown;
  cities?: KingdomCity[];
  equipment: EquipmentStock;
  identity: KingdomIdentity;
  leaders?: Leaders;
  metadata: KingdomMetadata;
  population: KingdomPopulation;
  ranks?: KingdomRanks;
  relations?: KingdomRelation[];
  wars?: KingdomWar[];
}

// This kingdom's diplomatic tie to one other — ally/enemy/neutral, with the net opinion score driving the tag colour.
export interface KingdomRelation { kingdom: EntityReference; opinion: { total: number }; status: 'ally' | 'enemy' | 'neutral' }

// `allies` is absent when a kingdom fights alone, both `*_alliance` when no alliance backs that side, `war_type` when WB never set one — `emit` strips them all.
export interface KingdomWar {
  allies?: EntityReference[];
  attacker_alliance?: EntityReference;
  cities: SideStats;
  deaths: SideStats;
  defender_alliance?: EntityReference;
  duration_years: number;
  id: number;
  name: string;
  opponents: EntityReference[];
  populations: SideStats;
  renown_at_stake: number;
  side: 'attacker' | 'defender';
  started_by: { actor?: PersonReference; kingdom: EntityReference };
  war_type?: 'conquest' | 'inspire' | 'rebellion' | 'spite' | 'whisper';
  warriors: SideStats;
}

// The kingdom's settlements, most populous first — chronicler-oriented list, also handy to resolve city names.
interface KingdomCity { id: number; name: string; population: number }

// What the crown officially is, and the ruler who opened it — its affiliations, never the counters `metadata` keeps.
interface KingdomIdentity {
  clan?: EntityReference;
  culture?: EntityReference;
  founder?: PersonReference;
  language?: EntityReference;
  religion?: EntityReference;
  subspecies?: EntityReference;
}

// The kingdom's own attributes (age, capital, king/heir/founder, resource stocks…) — as opposed to `population`, which aggregates its inhabitants.
interface KingdomMetadata {
  age: number;
  births?: number;
  book_reach?: number;
  books?: number; // volumes shelved across its towns, whoever wrote them
  buildings: number;
  capital?: EntityReference;
  cities: number;
  culture_traits?: number;
  deaths: number;
  food: number;
  foundings?: number;
  gold: number;
  goods: number;
  heir?: PersonReference;
  houses: number;
  id: number;
  kills: number;
  king?: PersonReference & { money: number };
  name: string;
  renown: number;
  score_rank: number;
  territory: number;
  wars_won?: number;
  wealth: number;
}

// Aggregates over the kingdom's inhabitants (wealth split, food/housing ratios) — distinct from the kingdom's own `metadata`. Its age/sex tallies and its
// `money` total are chronicler-only: the Richesse card sums the shares itself, so it never reads the total back.
interface KingdomPopulation {
  fed_pct: number;
  food_per_capita: number;
  housed_pct: number;
  immortals?: number;
  infected?: number;
  nobles_money: number;
  renown_total: number;
  sick?: number;
  subjects_money: number;
  total: number;
  warriors: number;
  wealth_per_capita: number;
}

// The kingdom's rank (1-3) per stat among all kingdoms, podium-only; its six money-share podiums stay chronicler-only — Richesse prints those shares bare.
interface KingdomRanks {
  age?: number;
  boats?: number;
  book_reach?: number;
  books?: number;
  buildings?: number;
  cities?: number;
  culture_traits?: number;
  deaths?: number;
  equipment?: number;
  food?: number;
  food_per_capita?: number;
  foundings?: number;
  goods?: number;
  housed_pct?: number;
  houses?: number;
  immortals?: number;
  infected?: number;
  kills?: number;
  population?: number;
  renown?: number;
  renown_total?: number;
  sick?: number;
  territory?: number;
  warriors?: number;
  wars_won?: number;
  wealth?: number;
  wealth_per_capita?: number;
}

// A per-side tally (attackers vs defenders) — reused for a war's population, warriors, cities and deaths.
interface SideStats { attackers: number; defenders: number }

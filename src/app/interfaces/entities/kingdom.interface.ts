import { EntityReference, EquipmentStock, HullCount, Leaders, PersonReference, PopulationBreakdown } from '../entity.interface';

// Absent, not empty: Python's `emit` strips `None`/`[]`/`{}`, so no podium, no neighbour or no ongoing war means no key at all.
export interface Kingdom {
  boats: HullCount;
  breakdown: PopulationBreakdown;
  gear: EquipmentStock;
  identity: KingdomIdentity;
  leaders?: Leaders;
  metadata: KingdomMetadata;
  population: KingdomPopulation;
  ranks?: KingdomRanks;
  relations?: KingdomRelation[];
  rulers?: [PersonReference]; // the sitting king alone, absent at an interregnum
}

// This kingdom's diplomatic tie to one other — ally/enemy/neutral, with the net opinion score driving the tag colour.
export interface KingdomRelation { kingdom: EntityReference; opinion: { total: number }; status: 'ally' | 'enemy' | 'neutral' }

// The ruler who opened the crown. What it officially is stays in `kingdom/info.py <id> identity`, each tier's own panel naming the favorite's.
interface KingdomIdentity { founder?: PersonReference }

// The kingdom's own attributes (age, capital, heir, resource stocks…) — as opposed to `population`, which aggregates its inhabitants.
interface KingdomMetadata {
  age: number;
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
  name: string;
  renown: number;
  score_rank?: number; // absent where the realm stands alone — a place needs a rival
  territory: number;
  wars_won?: number;
  wealth: number;
}

// Aggregates over the kingdom's inhabitants, not its `metadata` — age/sex tallies and the `money` total left to the chronicler, Richesse summing the shares.
interface KingdomPopulation {
  fed_pct?: number;
  food_per_capita?: number;
  housed_pct?: number;
  immortals?: number;
  infected?: number;
  nobles_money?: number;
  renown_total?: number;
  ruler_money?: number; // the king's own purse, the third share of `money` beside the nobles' and the subjects'
  sick?: number;
  subjects_money?: number;
  total: number;
  warriors?: number;
  wealth_per_capita?: number;
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
  food?: number;
  food_per_capita?: number;
  foundings?: number;
  gear?: number;
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

import { BookShelf, EntityReference, EquipmentStock, Leaders, PersonReference, PopulationBreakdown } from '../entity.interface';

// Absent, not empty: Python's `emit` strips `None`/`[]`/`{}`, so no podium (`ranks`) or an empty dimension means no key at all. A city is a kingdom's settlement.
export interface City {
  army?: CityArmy;
  books: BookShelf;
  breakdown: PopulationBreakdown;
  equipment: EquipmentStock;
  identity: CityIdentity;
  inventory: Record<string, number>; // WB's « Inventaire »: the itemised form of `metadata.food`, `gold` and `goods`
  leaders?: Leaders;
  loyalty: CityLoyalty;
  metadata: CityMetadata;
  population: CityPopulation;
  ranks?: CityRanks;
}

// The city's whole military, absent where there is none. `captain_years`, `kills_per_death` and `total_captains` ship in the JSON but stay chronicler-only.
interface CityArmy {
  age: number;
  captain?: PersonReference;
  deaths: number;
  kills: number;
  melee: number;
  money: number;
  name: string;
  ranged: number;
  renown: number;
}

// What the town officially answers to, and the settler who raised it — the bodies it is affiliated with, never what it counts.
interface CityIdentity {
  clan?: EntityReference;
  culture?: EntityReference;
  founder?: PersonReference;
  language?: EntityReference;
  religion?: EntityReference;
  subspecies?: EntityReference;
}

// How firmly the city holds to its crown: `new.py` keeps only the `total` for the reader, `city/info.py <id> loyalty` itemises the modifiers for the chronicler.
interface CityLoyalty { total: number }

// The city's own attributes (age, leader/founder, stocks…) — `population` aggregates its inhabitants instead. Its culture/language/religion ship chronicler-only.
interface CityMetadata {
  age: number;
  attractivity: number; // `migrated - left`, emitted whatever its sign — 0 and negatives are readings too
  births?: number;
  book_reach?: number;
  buildings: number;
  capital?: boolean;
  deaths: number;
  food: number;
  gold: number;
  goods: number;
  heir?: PersonReference;
  houses: number;
  id: number;
  kills: number;
  kingdom?: EntityReference;
  leader?: PersonReference & { money: number };
  name: string;
  renown: number;
  score_rank: number;
  territory: number;
  wealth: number;
}

// The city's inhabitants aggregated, not its `metadata`: `immortals`/`infected`/`sick` omitted at 0, age/sex tallies ship but stay chronicler-only.
interface CityPopulation {
  fed_pct: number;
  food_per_capita: number;
  housed_pct: number;
  immortals?: number;
  infected?: number;
  money: number;
  nobles_money: number;
  renown_total: number;
  sick?: number;
  subjects_money: number;
  total: number;
  warriors: number;
  wealth_per_capita: number;
}

// The city's rank (1-3) per stat among all cities, podium-only; the money ranks (`gold`, `money`, `nobles`) stay chronicler-only — Richesse prints them bare.
interface CityRanks {
  age?: number;
  army_age?: number;
  army_kills?: number;
  army_money?: number;
  army_renown?: number;
  attractivity?: number;
  book_reach?: number;
  books?: number;
  buildings?: number;
  deaths?: number;
  equipment?: number;
  food?: number;
  food_per_capita?: number;
  goods?: number;
  housed_pct?: number;
  houses?: number;
  immortals?: number;
  infected?: number;
  kills?: number;
  loyalty?: number;
  population?: number;
  renown?: number;
  renown_total?: number;
  sick?: number;
  territory?: number;
  warriors?: number;
  wealth?: number;
  wealth_per_capita?: number;
}

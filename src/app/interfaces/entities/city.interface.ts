import { BookShelf, EquipmentStock, Leaders, PersonReference, PopulationBreakdown } from '../entity.interface';

// Absent, not empty: Python's `emit` strips `None`/`[]`/`{}`, so no podium (`ranks`) or an empty dimension means no key at all. A city is a kingdom's settlement.
export interface City {
  army?: CityArmy;
  books: BookShelf;
  breakdown: PopulationBreakdown;
  gear: EquipmentStock;
  identity: CityIdentity;
  inventory?: Record<string, number>; // WB's « Inventaire »: the itemised form of `metadata.food`, `gold` and `goods`
  leaders?: Leaders;
  loyalty: CityLoyalty;
  metadata: CityMetadata;
  population: CityPopulation;
  ranks?: CityRanks;
  rulers?: [PersonReference]; // the sitting mayor alone, absent between two
}

// The city's whole military, absent where there is none. Its captains past and the sitting one's tenure stay in `city/info.py <id> army`.
interface CityArmy {
  age: number;
  captain?: PersonReference;
  deaths: number;
  kills: number;
  melee: number;
  money?: number;
  name: string;
  ranged: number;
  renown: number;
}

// The settler who raised the town. The bodies it answers to stay in `city/info.py <id> identity`, each tier's own panel naming the favorite's.
interface CityIdentity { founder?: PersonReference }

// How firmly the city holds to its crown: `new.py` keeps only the `total` for the reader, `city/info.py <id> loyalty` itemises the modifiers for the chronicler.
interface CityLoyalty { total: number }

// The city's own attributes (age, heir, stocks…) — `population` aggregates its inhabitants instead.
interface CityMetadata {
  age: number;
  attractivity: number; // `migrated - left`, emitted whatever its sign — 0 and negatives are readings too
  book_reach?: number;
  buildings: number;
  deaths: number;
  food: number;
  gold: number;
  goods: number;
  heir?: PersonReference;
  houses: number;
  id: number;
  kills: number;
  name: string;
  renown: number;
  score_rank?: number; // absent where the town stands alone — a place needs a rival
  territory: number;
  wealth: number;
}

// The city's inhabitants aggregated, not its `metadata`: `immortals`/`infected`/`sick` omitted at 0, age/sex tallies and the `money` total left to the chronicler.
interface CityPopulation {
  fed_pct?: number;
  food_per_capita?: number;
  housed_pct?: number;
  immortals?: number;
  infected?: number;
  nobles_money?: number;
  renown_total?: number;
  ruler_money?: number; // the mayor's own purse, the third share of `money` beside the nobles' and the subjects'
  sick?: number;
  subjects_money?: number;
  total: number;
  warriors?: number;
  wealth_per_capita?: number;
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
  food?: number;
  food_per_capita?: number;
  gear?: number;
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

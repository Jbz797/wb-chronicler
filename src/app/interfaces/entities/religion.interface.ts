import { BookShelf, Leaders, PersonReference, PopulationBreakdown, TierPopulation } from '../entity.interface';

// The favourite's religion: preached, not inherited — so its `breakdown` answers to no border, a creed crossing blood and crown one conversion at a time.
export interface Religion {
  books?: BookShelf; // volumes written under it, whoever holds them now — the mirror of a town's shelf, which counts what it holds whoever wrote it
  breakdown?: PopulationBreakdown; // absent where every dimension is shared by all
  identity: ReligionIdentity;
  leaders?: Leaders;
  metadata: ReligionMetadata;
  pop?: TierPopulation; // absent where no member lives in a town — Python omits an empty block
  ranks?: ReligionRanks;
  traits: string; // the chronicler's summary, carried forward while neither the entity nor its traits move
}

// The founder's card, as WB's own window lays it out — Python ships it whole, of which the panel names the founder alone and the chronicler keeps the rest.
interface ReligionIdentity { founder?: PersonReference }

// Every counter drops at zero, so panels read them via `?? 0`. `cities`/`kingdoms` are WB's own reach: those holding it, not merely housing a believer.
interface ReligionMetadata {
  age: number;
  cities?: number;
  deaths?: number;
  id: number;
  kills?: number;
  kingdoms?: number;
  members?: number; // its living, counted: `world … roster --religion <id>` names them
  name: string;
  renown?: number;
}

// Podium-only, like every other tier: absent where the religion places outside the top 3 among the world's creeds.
interface ReligionRanks {
  age?: number;
  books?: number;
  cities?: number;
  deaths?: number;
  housed_pct?: number;
  kills?: number;
  kingdoms?: number;
  members?: number;
  money?: number;
  renown?: number;
  renown_total?: number;
  warriors?: number;
}

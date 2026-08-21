import { BookShelf, Leaders, MemberRoster, PersonReference, PopulationBreakdown, TierPopulation } from './entity.interface';
import { TraitGroupCounts } from './types';

// The favourite's culture: caught at the cradle, not sworn — so its `breakdown` drifts furthest from the founder whose card `identity` holds.
export interface Culture {
  books: BookShelf; // volumes written under it, whoever holds them now — the mirror of a town's shelf, which counts what it holds whoever wrote it
  breakdown: PopulationBreakdown;
  identity: CultureIdentity;
  leaders?: Leaders;
  members: MemberRoster;
  metadata: CultureMetadata;
  population: TierPopulation;
  ranks?: CultureRanks;
  traits: TraitGroupCounts;
}

// The founder's card, as WB's own window lays it out — Python ships all seven, of which the panel names the founder alone and the chronicler keeps the rest.
interface CultureIdentity {
  founder?: PersonReference;
}

// Every counter drops at zero, so panels read them via `?? 0`. `cities`/`kingdoms` are WB's own reach: those holding it as their main culture, not just housing it.
interface CultureMetadata {
  age: number;
  cities?: number;
  deaths?: number;
  id: number;
  kills?: number;
  kingdoms?: number;
  name: string;
  renown?: number;
  traits?: number;
}

// Podium-only, like every other tier: absent where the culture places outside the top 3 among the world's cultures.
interface CultureRanks {
  age?: number;
  books?: number;
  cities?: number;
  deaths?: number;
  kills?: number;
  kingdoms?: number;
  members?: number;
  money?: number;
  renown?: number;
  renown_total?: number;
  traits?: number;
}

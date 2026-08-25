import { BookShelf, Leaders, MemberRoster, PersonReference, PopulationBreakdown, TierPopulation } from '../entity.interface';

// The favourite's language: caught by ear, not by blood — so WB counts its speakers three ways, born to it, won from another tongue, and lost to one.
export interface Language {
  books: BookShelf; // volumes still written in it, whoever holds them now — `metadata.written` is WB's lifetime tally, burnt ones counted
  breakdown: PopulationBreakdown;
  identity: LanguageIdentity;
  leaders?: Leaders;
  members: MemberRoster; // those who answer in it — WB points the actor at its tongue, never the reverse
  metadata: LanguageMetadata;
  population: TierPopulation;
  ranks?: LanguageRanks;
  traits: string; // the chronicler's summary, carried forward while neither the entity nor its traits move
}

// The founder's card, as WB's own window lays it out — Python ships it whole, of which the panel names the founder alone and the chronicler keeps the rest.
interface LanguageIdentity { founder?: PersonReference }

// Every counter drops at zero, so panels read them via `?? 0`. `cities`/`kingdoms` are WB's own reach: those WB records as speaking it, not merely housing one.
interface LanguageMetadata {
  age: number;
  cities?: number;
  converted?: number;
  deaths?: number;
  id: number;
  kills?: number;
  kingdoms?: number;
  lost?: number;
  name: string;
  native?: number;
  renown?: number;
  traits?: number;
  written?: number;
}

// Podium-only, like every other tier: absent where the language places outside the top 3 among the world's tongues.
interface LanguageRanks {
  age?: number;
  books?: number;
  books_written?: number;
  cities?: number;
  converted?: number;
  deaths?: number;
  fed_pct?: number;
  housed_pct?: number;
  kills?: number;
  kingdoms?: number;
  lost?: number;
  members?: number;
  money?: number;
  native?: number;
  renown?: number;
  renown_total?: number;
  warriors?: number;
}

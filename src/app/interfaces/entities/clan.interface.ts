import { Leaders, MemberRoster, PersonReference, PopulationBreakdown, TierPopulation } from '../entity.interface';

// The favourite's clan. Joined, not inherited — so unlike its `Family`, its members share colours rather than blood, and its `traits` are sworn to.
export interface Clan {
  breakdown?: PopulationBreakdown; // absent where every dimension is shared by all
  identity: ClanIdentity;
  leaders?: Leaders;
  members: MemberRoster;
  metadata: ClanMetadata;
  population: TierPopulation;
  ranks?: ClanRanks;
  traits: string; // the chronicler's summary, carried forward while neither the entity nor its traits move
}

// Who founded the band. Its culture and the stock it sprang from stay in `clan/info.py <id> identity`.
interface ClanIdentity { founder?: PersonReference }

// Every counter drops at zero, so panels read them via `?? 0` — bar `past_chiefs`, which WB never leaves empty and the panel prints directly.
interface ClanMetadata {
  age: number;
  books_written?: number;
  chief?: PersonReference;
  cities?: number;
  deaths?: number;
  heir?: PersonReference;
  id: number;
  kills?: number;
  kingdoms?: number;
  name: string;
  past_chiefs: number;
  renown?: number;
}

// Podium-only, like every other tier: absent where the clan places outside the top 3 among the world's clans.
interface ClanRanks {
  age?: number;
  books_written?: number;
  deaths?: number;
  kills?: number;
  kingdoms?: number;
  members?: number;
  money?: number;
  renown?: number;
  renown_total?: number;
}

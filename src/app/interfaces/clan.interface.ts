import { MemberRoster, PersonReference, PopulationBreakdown } from './entity.interface';
import { TraitGroupCounts } from './types';

// The favourite's clan. Joined, not inherited — so unlike its `Family`, its members share colours rather than blood, and its `traits` are sworn to.
export interface Clan {
  breakdown: PopulationBreakdown;
  members: MemberRoster;
  metadata: ClanMetadata;
  ranks?: ClanRanks;
  traits: TraitGroupCounts;
}

// Every counter drops at zero, so panels read them via `?? 0` — bar `past_chiefs`, which WB never leaves empty and the panel prints directly.
interface ClanMetadata {
  age: number;
  births?: number;
  books_written?: number;
  chief?: PersonReference;
  cities?: number;
  deaths?: number;
  founder?: PersonReference;
  heir?: PersonReference;
  id: number;
  kills?: number;
  kingdoms?: number;
  money?: number; // summed over the living, not a WB field — a clan has no purse of its own, its members do
  name: string;
  past_chiefs: number;
  renown?: number;
  renown_total?: number; // summed over the living, where `renown` above is WB's own field for the clan — a famous name can be worn by nobodies
  traits?: number;
}

// Podium-only, like every other tier: absent where the clan places outside the top 3 among the world's clans.
interface ClanRanks {
  age?: number;
  births?: number;
  books_written?: number;
  deaths?: number;
  kills?: number;
  members?: number;
  money?: number;
  renown?: number;
  renown_total?: number;
  traits?: number;
}

import { Leaders, MemberRoster, PersonReference, PopulationBreakdown, TierPopulation } from '../entity.interface';

// The favourite's bloodline. A lineage, not a household — `houses` counts the roofs its members sleep under, rarely one. The roster stays chronicler-only.
export interface Family {
  breakdown: PopulationBreakdown;
  leaders?: Leaders;
  members: MemberRoster;
  metadata: FamilyMetadata;
  population: TierPopulation;
  ranks?: FamilyRanks;
}

// Every counter drops at zero, so panels read them via `?? 0` — what the living themselves are worth now sits in `population`, as it does on the other tiers.
interface FamilyMetadata {
  age: number;
  alpha?: PersonReference;
  births?: number;
  cities?: number;
  deaths?: number;
  founders: PersonReference[];
  houses?: number;
  id: number;
  kills?: number;
  name: string;
}

// Podium-only, like every other tier: absent where the lineage places outside the top 3 among the world's families.
interface FamilyRanks {
  age?: number;
  births?: number;
  cities?: number;
  deaths?: number;
  houses?: number;
  kills?: number;
  members?: number;
  money?: number;
  renown_total?: number;
}

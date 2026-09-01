import { Leaders, MemberRoster, PersonReference, PopulationBreakdown, TierPopulation } from '../entity.interface';

// The favourite's bloodline. A lineage, not a household — `houses` counts the roofs its members sleep under, rarely one. The roster stays chronicler-only.
export interface Family {
  breakdown: PopulationBreakdown;
  identity: FamilyIdentity;
  leaders?: Leaders;
  members: MemberRoster;
  metadata: FamilyMetadata;
  population: TierPopulation;
  ranks?: FamilyRanks;
}

// Who opened the line — WB seats a lineage on one founder or a founding couple, and the panel titles each after their own sex.
interface FamilyIdentity { founders: PersonReference[] }

// Every counter drops at zero, so panels read them via `?? 0` — what the living themselves are worth now sits in `population`, as it does on the other tiers.
interface FamilyMetadata {
  age: number;
  alpha?: PersonReference;
  births?: number;
  cities?: number;
  deaths?: number;
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

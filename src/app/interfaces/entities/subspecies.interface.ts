import { Leaders, MemberRoster, PopulationBreakdown, TierPopulation } from '../entity.interface';

// The stock's standing among the world's species — flat counts beside its own podium; `id` stays out of `SpeciesTotals`, which the podium reads as `keyof`.
export interface SpeciesStanding extends SpeciesTotals { id: string; ranks?: Partial<SpeciesTotals> }

// Living counts over a whole species, those the panel shows plus the biologies WB mutated out of it. Each drops at zero, so panels read them via `?? 0`.
export interface SpeciesTotals {
  cities?: number;
  kingdoms?: number;
  population?: number;
  renown?: number;
  subspecies?: number;
}

// The favourite's subspecies. Neither joined nor inherited but born into — WB fixes it at birth, so its bearers span every crown and clan without ever choosing it.
export interface Subspecies {
  breakdown: PopulationBreakdown;
  leaders?: Leaders;
  members: MemberRoster;
  metadata: SubspeciesMetadata;
  population: TierPopulation;
  ranks?: SubspeciesRanks;
  species: SpeciesStanding;
  traits: string; // the chronicler's summary of its biology and of what its newborns inherit — `subspecies/info.py <id> traits` keeps the two apart
}

// Every counter is dropped at zero, WB's own and ours alike — a beast holds no town and swears no trait, and the panels read them through `?? 0`.
interface SubspeciesMetadata {
  age: number;
  biome?: string; // WB's key, translated by `BIOME_NAMES`; absent where it set no variant at all, which drops the row
  births?: number;
  cities?: number;
  deaths?: number;
  id: number;
  kills?: number;
  kingdoms?: number;
  name: string;
  renown?: number;
}

// Podium-only, like every other tier: absent where the biology places outside the top 3 among the world's subspecies.
interface SubspeciesRanks {
  age?: number;
  births?: number;
  deaths?: number;
  kills?: number;
  members?: number;
  money?: number;
  renown?: number;
  renown_total?: number;
}

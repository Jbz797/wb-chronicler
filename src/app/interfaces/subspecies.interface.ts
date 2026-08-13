import { MemberRoster, PopulationBreakdown } from './entity.interface';
import { RarityCounts } from './stats.interface';

// A species as the panel shows it: what it is, and where it places among the world's species — the same `metadata`/`ranks` pair every other tier carries.
export interface SpeciesStanding {
  asset_id: string;
  metadata: SpeciesTotals;
  name: string;
  ranks?: Partial<SpeciesTotals>;
}

// Living counts over a whole species, the four the panel shows plus the biologies WB has mutated out of it.
export interface SpeciesTotals {
  cities: number;
  kingdoms: number;
  population: number;
  renown: number;
  subspecies: number;
}

// The favourite's subspecies. Neither joined nor inherited but born into — WB fixes it at birth, so its bearers span every crown and clan without ever choosing it.
export interface Subspecies {
  birth_traits: RarityCounts; // what every newborn of it inherits, off the same creature library the favourite draws from — hence the same rarity axis
  breakdown: PopulationBreakdown;
  identity: SubspeciesIdentity;
  members: MemberRoster;
  metadata: SubspeciesMetadata;
  ranks?: SubspeciesRanks;
}

// What it was mutated out of and what shaped it — Python names both off WB's French sheets, and the stock carries its standing among the world's species.
interface SubspeciesIdentity {
  biome: string | null; // WB's key, translated by `BIOME_NAMES`; `null` where it set no variant at all, which drops the row
  species: SpeciesStanding;
}

interface SubspeciesMetadata {
  age: number;
  births?: number;
  cities: number;
  deaths?: number;
  id: number;
  kills?: number;
  kingdoms: number;
  money: number;
  name: string;
  renown: number;
  renown_total: number; // summed over the living, where `renown` above is WB's own tally over every bearer ever born
  traits: number;
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
  traits?: number;
}

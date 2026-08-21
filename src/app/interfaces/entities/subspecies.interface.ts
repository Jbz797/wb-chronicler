import { Leaders, MemberRoster, PopulationBreakdown, TierPopulation } from '../entity.interface';
import { TraitGroupCounts } from '../types';

// The stock's standing among the world's species — flat counts beside its own podium, as a realm's `alliance` carries its two.
export interface SpeciesStanding extends SpeciesTotals {
  description?: string;
  ranks?: Partial<SpeciesTotals>;
}

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
  identity: SubspeciesIdentity;
  leaders?: Leaders;
  members: MemberRoster;
  metadata: SubspeciesMetadata;
  population: TierPopulation;
  ranks?: SubspeciesRanks;
  species: SpeciesStanding;
  traits: TraitGroupCounts; // its biology and what its newborns inherit, pooled per WB trait group — `subspecies/info.py <id> traits` keeps the two apart
}

// What it was mutated out of and what shaped it — Python names both off WB's French sheets, and the stock carries its standing among the world's species.
interface SubspeciesIdentity {
  biome: string | null; // WB's key, translated by `BIOME_NAMES`; `null` where it set no variant at all, which drops the row
  species: string; // its `asset_id`, translated by `SPECIES_NAMES` — the standing lives in the `species` section beside
}

// Every counter is dropped at zero, WB's own and ours alike — a beast holds no town and swears no trait, and the panels read them through `?? 0`.
interface SubspeciesMetadata {
  age: number;
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

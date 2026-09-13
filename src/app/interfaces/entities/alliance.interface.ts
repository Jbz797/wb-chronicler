import { EntityReference, Leaders, PopulationBreakdown, TierPopulation } from '../entity.interface';

// A pact of crowns, and the one tier the favourite reaches through another: his kingdom's. Absent, not empty — Python's `emit` strips `None`/`[]`/`{}`.
export interface Alliance {
  breakdown: PopulationBreakdown;
  identity: AllianceIdentity;
  kingdoms: AllianceKingdom[];
  leaders?: Leaders;
  metadata: AllianceMetadata;
  population: TierPopulation;
  ranks?: AllianceRanks;
}

// What the pact was sworn as: the soul who signed and the crown that opened it, both of whom it may long outlive.
interface AllianceIdentity { founder?: EntityReference }

// A member realm, with what it brings to the pool.
interface AllianceKingdom { id: number; name: string; population: number }

// WB keeps a pact's lifetime counters apart from its members' — these are its own, never their sum. Each drops at zero, so the panel reads them through `?? 0`.
interface AllianceMetadata {
  age: number;
  births?: number;
  buildings?: number;
  deaths?: number;
  id: number;
  kills?: number;
  name: string; // read by the panel's header chip, not by any row — the tag beside the title carries it
  population: number; // pooled from its realms, where a sworn body would count a roster
  renown?: number;
}

interface AllianceRanks {
  age?: number;
  buildings?: number;
  deaths?: number;
  kills?: number;
  population?: number;
  renown?: number;
  territory?: number;
  warriors?: number;
}

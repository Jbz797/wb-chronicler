import { EntityReference } from '../entity.interface';

// One war read from above, neither camp being « ours » — both are named as WB names them, and a side with no pact carries no `alliance` key at all.
export interface War { attackers: WarSide; defenders: WarSide; metadata: WarMetadata }

interface WarKingdom { id: number; name: string; population: number }

// WB's counters on the war, and where it comes from. No `identity` block: a war swears to no culture or stock, and one line is no section.
interface WarMetadata {
  age: number;
  deaths: number;
  id: number;
  name: string;
  renown_at_stake: number;
  started_by: { id: number; name?: string }; // the soul who spoke for it — WB keeps his id but not his name, so the name drops once he dies
  started_by_kingdom: EntityReference;
  war_type?: 'conquest' | 'inspire' | 'rebellion' | 'spite' | 'whisper'; // WB leaves it unset on most declarations — absence is not `none`
}

// One camp: the realms fielding, and what they bring between them. `alliance` names the pact backing them, where two of its members stand together.
interface WarSide {
  alliance?: EntityReference;
  cities: number;
  deaths: number;
  kingdoms: WarKingdom[];
  population: number;
  warriors: number;
}

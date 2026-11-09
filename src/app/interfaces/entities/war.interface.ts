import { EntityReference } from '../entity.interface';

// One war read from above, neither camp being « ours » — both are named as WB names them, and a side with no pact carries no `alliance` key at all.
export interface War { attackers: WarSide; defenders: WarSide; metadata: WarMetadata }

interface WarKingdom { id: number; name: string }

// WB's counters on the war, and where it comes from. No `identity` block: a war swears to no culture or stock, and one line is no section.
interface WarMetadata {
  age: number;
  balance?: number; // who holds the upper hand, in % for the attackers — 50 even; absent from a chapter older than it
  id: number;
  name: string;
  renown_at_stake: number;
  started_by_kingdom: EntityReference;
  war_type?: 'conquest' | 'inspire' | 'rebellion' | 'spite' | 'whisper'; // WB leaves it unset on most declarations — absence is not `none`
}

// One camp: the realms fielding, and what they bring between them. `alliance` names the pact backing them, where two of its members stand together.
interface WarSide {
  alliance?: EntityReference;
  cities: number;
  deaths: number;
  kingdoms: WarKingdom[];
  nobles?: number; // kings, town heads and captains struck down since the declaration — absent at 0
  pop: number;
  taken?: number; // towns come under the camp's banner since the declaration, taken or won over — absent at 0
  warriors: number;
}

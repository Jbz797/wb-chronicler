import { EntityReference } from '../entity.interface';

// The hull the favorite is aboard, absent otherwise — WB models boats as actors, so it holds no renown and no purse of its own.
export interface Boat { crew: BoatCrew; identity: BoatIdentity; metadata: BoatMetadata }

// Souls aboard this instant, counted and nothing more — the roster stays behind in `boat/info.py <id> crew`, where the chronicler reads it.
interface BoatCrew { total: number }

// What the hull is, read off its `asset_id`: WB names barely a tenth of a world's boats, so the asset carries the identity a name would — its trade chronicler-only.
interface BoatIdentity {
  city?: EntityReference;
  kingdom?: EntityReference;
  name?: string;
  species?: string; // the stock whose docks laid the keel; a fishing skiff names none
}

// The hull itself: how long it has floated, how battered, and where it sits — WB gives a boat health, never renown.
interface BoatMetadata { age: number; health: number; health_max: number }

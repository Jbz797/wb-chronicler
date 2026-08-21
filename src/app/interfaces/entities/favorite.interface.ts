import { EntityReference, PersonReference } from '../entity.interface';
import { RarityCounts } from '../stats.interface';
import { LifeStage } from '../types';

// Absent, never null: `emit` strips `None`/`[]`/`{}` — no lover, no plot, an empty bag or no top-3 rank means no key. `descriptor` is authored by the chronicler.
export interface Favorite {
  companions?: Companions;
  descriptor: string;
  inventory?: Record<string, number>;
  metadata: FavoriteMetadata;
  plot?: Plot;
  ranks_in_species?: FavoriteRanks;
  stats: FavoriteStats;
  traits: RarityCounts;
}

// The favorite's two attachments. Python emits each with its full stat line for the chronicler; the UI only ever draws their `[p]` tag, hence `EntityReference`.
interface Companions { best_friend?: PersonReference; lover?: PersonReference }

// The favorite's identity and civic standing (species, kingdom, roles…); optional fields are dropped by Python when the actor has none.
interface FavoriteMetadata {
  age: number;
  asset_id: string;
  city?: EntityReference;
  id: number;
  job: string;
  kingdom?: EntityReference;
  life_stage: LifeStage;
  name: string;
  personality?: string;
  roles?: string[];
  sex: 'female' | 'male';
  tenure_years?: number;
}

// The favorite's rank (1-3) per stat among its species peers — all optional: a stat is absent when the favorite isn't on its podium.
interface FavoriteRanks {
  age?: number;
  armor?: number;
  attack_speed?: number;
  children?: number;
  critical_chance?: number;
  damage?: number;
  diplomacy?: number;
  equipment_power?: number;
  health_max?: number;
  intelligence?: number;
  kills?: number;
  level?: number;
  lifespan?: number;
  mana_max?: number;
  money?: number;
  renown?: number;
  speed?: number;
  stamina_max?: number;
  stewardship?: number;
  warfare?: number;
}

// The favorite's raw combat / social / vital stats — WB runtime values, always present.
interface FavoriteStats {
  armor: number;
  attack_speed: number;
  children: number;
  critical_chance: number;
  damage: number;
  diplomacy: number;
  equipment_power: number;
  happiness?: number; // absent where the biology bears no `amygdala`: WB grants such a soul no emotions, and writes it no happiness either
  health: number;
  health_max: number;
  intelligence: number;
  kills: number;
  level: number;
  lifespan: number;
  mana: number;
  mana_max: number;
  max_children: number;
  money: number;
  nutrition: number;
  renown: number;
  speed: number;
  stamina: number;
  stamina_max: number;
  stewardship: number;
  warfare: number;
}

// The favorite's active scheme (WB `Plot`); `target_*` are absent when the plot has no such target.
interface Plot { name: string; progress: number; target_alliance?: EntityReference; target_kingdom?: EntityReference; type_id: string }

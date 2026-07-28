export interface CityInfo { color: string; dead?: boolean; ink: string; name?: string; size?: number; species?: string }
export interface KingdomInfo { cities?: number; color: string; dead?: boolean; name?: string; rank?: number; species?: string }

// Everything `<app-actor-portrait>` needs to draw the actor. Python omits `head`/`phenotype_*` at 0 — WB's own default; the entry's `name` is chronicler-only.
export interface PersonInfo {
  asset_id: string;
  dead?: boolean;
  head?: number;
  kingdom?: number;
  phenotype_index?: number;
  phenotype_shade?: number;
  profession?: string;
  sex?: string;
  special_head?: string;
  weapon?: string;
}

export interface WorldInfo { description: string; name: string }

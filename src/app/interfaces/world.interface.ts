// A settlement's tag visuals: `crown` names the sprite (`capital`/`city`), and `kingdom` fetches every hue it wears — name, medallion, crown ramp and ring alike.
export interface CityInfo {
  crown?: string;
  dead?: boolean;
  kingdom?: number;
  rank?: number;
  size?: number;
  species?: string;
}

// A realm's tag visuals: the `banner_*` four are the shield and emblem slots `KingdomSpriteHelpers` composes, each with its hue; its `name` is chronicler-only.
export interface KingdomInfo {
  banner_bg?: number;
  banner_bg_color?: string;
  banner_icon?: number;
  banner_icon_color?: string;
  cities?: number;
  color: string;
  dead?: boolean;
  rank?: number;
  species?: string;
}

// Everything `ActorSpriteHelpers` needs to draw the actor. Python omits `head`/`phenotype_*` at 0 — WB's own default; the entry's `name` is chronicler-only.
export interface PersonInfo {
  asset_id: string;
  dead?: boolean;
  head?: number;
  kingdom?: number;
  level?: number;
  phenotype_index?: number;
  phenotype_shade?: number;
  profession?: string;
  sex?: string;
  special_head?: string;
  weapon?: string;
}

export interface WorldInfo { description: string; name: string }

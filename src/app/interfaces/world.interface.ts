// A settlement's tag visuals: `plate` names WB's own nameplate (`capital`/`city`), which is what sets a seat apart, and `kingdom` fetches the name's hue.
export interface CityInfo {
  dead?: boolean;
  kingdom?: number;
  plate?: string;
  rank?: number;
  size?: number;
  species?: string;
}

// A clan's tag: its own hue (sworn, not granted, so no crown lends it one), the founder's species pip and the living headcount. Its `name` survives extinction.
export interface ClanInfo {
  banner_bg?: number;
  banner_bg_color?: string;
  banner_icon?: number;
  banner_icon_color?: string;
  color: string;
  dead?: boolean;
  members?: number;
  name: string;
  species?: string;
}

// A lineage's tag: the frame worn as a border, the flattened backing hue, the founding species' pip and its living headcount. Its `name` survives extinction.
export interface FamilyInfo {
  bg_color?: string;
  dead?: boolean;
  frame?: number;
  members?: number;
  name: string;
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
  color_main?: string;
  dead?: boolean;
  rank?: number;
  species?: string;
}

// Everything `ActorSpriteHelpers` needs to draw the actor. Python omits `head`/`phenotype_*` at 0 — WB's own default; the entry's `name` is chronicler-only.
export interface PersonInfo {
  asset_id: string;
  dead?: boolean;
  head?: number;
  job?: string;
  kingdom?: number;
  level?: number;
  phenotype_index?: number;
  phenotype_shade?: number;
  sex?: string;
  skin_id?: number;
  special_head?: string;
  weapon?: string;
}

// A biology's tag: the stone slab its name is written on, the two hues WB dyes its bookmark in, the species it was mutated out of, and its living bearers.
export interface SubspeciesInfo {
  banner_bg?: number;
  color: string;
  color_main?: string;
  color_main_2?: string;
  dead?: boolean;
  members?: number;
  name: string;
  species?: string;
}

export interface WorldInfo { description: string; name: string }

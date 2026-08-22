// A volume's tag: the two sheets its sprite stacks — a cover from the common set, its genre's white glyph over it — and the hue WB prints its title in.
export interface BookInfo {
  color?: string;
  cover?: string;
  dead?: boolean; // burnt since this chapter: WB drops it from `save.books`, the registry keeps its board and strikes the title through
  icon?: string; // `<genre folder>/<sheet>`, the folder parting from the genre id for `bad_story_about_king` alone
  name: string;
  rank?: number; // podium place by readings, top 3 only — the medal right of the name
  reads?: number;
}

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
  name: string;
  rank?: number; // podium place by members, top 3 only — the medal right of the name
  size?: number;
  species?: string;
}

// A culture's tag: its own hue (caught, not granted, so no crown lends it one), the founder's species pip and the living headcount. Its `name` survives extinction.
export interface CultureInfo {
  banner_bg?: number;
  banner_bg_color?: string;
  banner_icon?: number;
  banner_icon_color?: string;
  color: string;
  dead?: boolean;
  name: string;
  rank?: number; // podium place by followers, top 3 only — the medal right of the name
  size?: number;
  species?: string;
}

// A lineage's tag: the frame worn as a border, the flattened backing hue, the founding species' pip and its living headcount. Its `name` survives extinction.
export interface FamilyInfo {
  bg_color?: string;
  dead?: boolean;
  frame?: number;
  name: string;
  rank?: number; // podium place by members, top 3 only — the medal right of the name
  size?: number;
  species?: string;
}

// A realm's tag visuals: the `banner_*` four are the shield and emblem slots `KingdomSpriteHelpers` composes, each with its hue; its `name` is chronicler-only.
export interface KingdomInfo {
  banner_bg?: number;
  banner_bg_color?: string;
  banner_icon?: number;
  banner_icon_color?: string;
  color: string;
  color_main?: string;
  dead?: boolean;
  rank?: number;
  size?: number;
  species?: string;
}

// A tongue's tag: its own hue (caught, not granted, so no crown lends it one), the founder's species pip and the living speakers. Its `name` survives extinction.
export interface LanguageInfo {
  banner_bg?: number;
  banner_bg_color?: string;
  banner_icon?: number;
  banner_icon_color?: string;
  color: string;
  dead?: boolean;
  name: string;
  rank?: number; // podium place by population, top 3 only — the medal right of the name
  size?: number;
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
  rank?: number; // podium place by level, top 3 only — the medal right of the name
  sex?: string;
  skin_id?: number;
  special_head?: string;
  weapon?: string;
}

// A creed's tag: its own hue (preached, not granted, so no crown lends it one), the founder's species pip and the living faithful. Its `name` survives extinction.
export interface ReligionInfo {
  banner_bg?: number;
  banner_bg_color?: string;
  banner_icon?: number;
  banner_icon_color?: string;
  color: string;
  dead?: boolean;
  name: string;
  rank?: number; // podium place by faithful, top 3 only — the medal right of the name
  size?: number;
  species?: string;
}

// A biology's tag: the stone slab its name is written on, the two hues WB dyes its bookmark in, the species it was mutated out of, and its living bearers.
export interface SubspeciesInfo {
  banner_bg?: number;
  color: string;
  color_main?: string;
  color_main_2?: string;
  dead?: boolean;
  name: string;
  rank?: number; // podium place by bearers, top 3 only — the medal right of the name
  size?: number;
  species?: string;
}

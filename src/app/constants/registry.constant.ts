import {
  AllianceRegistry, BookRegistry, CityRegistry, ClanRegistry, CultureRegistry, FamilyRegistry, KingdomRegistry, LanguageRegistry, PersonRegistry, ReligionRegistry,
  SubspeciesRegistry,
} from '../interfaces';

export const ALLIANCE_REGISTRY: AllianceRegistry = {};
export const BOOK_REGISTRY: BookRegistry = {};
export const CITY_REGISTRY: CityRegistry = {};
export const CITY_SIZE_TERMS = ['ui_homestead', 'ui_hamlet', 'ui_village', 'ui_town', 'ui_large_town', 'ui_city', 'ui_great_city', 'ui_metropolis', 'ui_world_city'];
export const CLAN_REGISTRY: ClanRegistry = {};
export const CULTURE_REGISTRY: CultureRegistry = {};
export const FAMILY_REGISTRY: FamilyRegistry = {};
export const KINGDOM_REGISTRY: KingdomRegistry = {};
export const KINGDOM_SIZE_TERMS = ['ui_landless_name', 'ui_city_state', 'ui_lordship', 'ui_kingdom', 'ui_great_kingdom', 'ui_empire'];
export const LANGUAGE_REGISTRY: LanguageRegistry = {};
export const PERSON_REGISTRY: PersonRegistry = {};
export const REALM_FALLBACK_HUE = '#B0B0B0'; // WB `Toolbox.color_grey` — worn by whoever answers to no crown: wild beasts, bandits, the exiled.
export const RELIGION_REGISTRY: ReligionRegistry = {};
export const SUBSPECIES_REGISTRY: SubspeciesRegistry = {};

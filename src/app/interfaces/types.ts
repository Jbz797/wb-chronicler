import { INLINE_MARKER } from '../constants/marker.constant';

import {
  AllianceInfo, BookInfo, CityInfo, ClanInfo, CultureInfo, FamilyInfo, KingdomInfo, LanguageInfo, PersonInfo, ReligionInfo, SubspeciesInfo,
} from './registry.interface';

export type ActorRect = [number, number, number, number, number]; // x, y, width, height, pivot drop from the top — a part sits where its pivot meets the anchor's.
export type AllianceRegistry = Record<string, AllianceInfo>;
export type BookRegistry = Record<string, BookInfo>;
export type BreakdownSource = Exclude<ChapterTier, 'favorite'>; // a « Composition » needs a population, and the favourite is one soul
export type ChapterOverviewPanel = 'wars' | 'world-stats' | ChapterTier; // the collapse's panels: every tier, plus the world and the wars, which are no tier

// Every body a chapter names, and the four types below are cut from it. `ChapterMeta extends Record<ChapterTier, unknown>` closes the loop from downstream.
export type ChapterTier = 'alliance' | 'city' | 'clan' | 'culture' | 'family' | 'favorite' | 'kingdom' | 'language' | 'religion' | 'subspecies';

export type CityMetaStat = 'age' | 'attractivity' | 'book_reach' | 'buildings' | 'deaths' | 'food' | 'goods' | 'houses' | 'kills' | 'renown'
  | 'territory' | 'wealth';

export type CityRegistry = Record<string, CityInfo>;
export type ClanRegistry = Record<string, ClanInfo>;
export type CultureRegistry = Record<string, CultureInfo>;
export type CumulativeStat = 'books_burnt' | 'books_read' | 'cities_conquered' | 'cities_rebelled' | 'evolutions' | 'metamorphosis' | 'plots_succeeded';

export type DeathCause = 'acid' | 'divine' | 'drowning' | 'eaten' | 'explosion' | 'fire' | 'gravity' | 'hunger'
  | 'infection' | 'old_age' | 'other' | 'plague' | 'poison' | 'tumor' | 'water' | 'weapon';

export type FamilyRegistry = Record<string, FamilyInfo>;

export type IconKind = 'alliances' | 'boats' | 'books' | 'cities' | 'clans' | 'cultures' | 'families' | 'kingdoms' | 'languages' | 'persons'
  | 'religions' | 'resources' | 'species' | 'subspecies' | 'wars';

export type InlineMarker = (typeof INLINE_MARKER)[keyof typeof INLINE_MARKER];

// A realm's own metrics — listed in full, not extended from `CityMetaStat`: a crown has no `attractivity`, nobody migrates to a realm.
export type KingdomMetaStat = 'age' | 'book_reach' | 'books' | 'buildings' | 'cities' | 'culture_traits' | 'deaths' | 'food' | 'foundings' | 'goods'
  | 'houses' | 'kills' | 'renown' | 'territory' | 'wars_won' | 'wealth';

export type KingdomRegistry = Record<string, KingdomInfo>;
export type LanguageRegistry = Record<string, LanguageInfo>;

export type LeaderKind = 'dominant_culture' | 'dominant_language' | 'dominant_religion' | 'dominant_species' | 'dominant_subspecies'
  | 'highest_level_person' | 'largest_city' | 'largest_clan' | 'largest_family' | 'largest_kingdom'
  | 'most_dominant_village' | 'most_powerful_kingdom';

export type LifeStage = 'adult' | 'baby' | 'child' | 'egg' | 'elder' | 'teen';
export type PeopleTierName = Exclude<ChapterTier, 'city' | 'favorite' | 'kingdom'>; // those `_resolvePeople` serves — the bodies that roster the living
export type PersonRegistry = Record<string, PersonInfo>;
export type PopulationStat = 'fed_pct' | 'food_per_capita' | 'housed_pct' | 'immortals' | 'infected' | 'renown_total' | 'sick' | 'warriors' | 'wealth_per_capita';

export type RankedStatKind = 'age' | 'armor'
  | 'army_age' | 'army_deaths' | 'army_kills' | 'army_melee' | 'army_money' | 'army_ranged' | 'army_renown'
  | 'attack_speed' | 'attractivity' | 'births' | 'boats' | 'book_reach' | 'books' | 'books_written' | 'buildings' | 'children' | 'cities' | 'converted'
  | 'critical_chance' | 'culture_traits' | 'damage' | 'deaths'
  | 'diplomacy' | 'equipment' | 'equipment_power' | 'fed_pct' | 'food' | 'food_per_capita' | 'foundings'
  | 'goods' | 'health' | 'housed_pct' | 'houses' | 'immortals' | 'infected' | 'intelligence' | 'kills' | 'kingdoms' | 'level' | 'lifespan' | 'lost' | 'loyalty'
  | 'mana' | 'members' | 'money'
  | 'native' | 'population' | 'renown' | 'renown_total' | 'score_rank' | 'sick' | 'speed' | 'stamina' | 'stewardship' | 'subspecies' | 'territory'
  | 'warfare' | 'warriors' | 'wars_won' | 'wealth' | 'wealth_per_capita';

export type RankedStatSource = 'alliance' | 'species' | ChapterTier; // a tier, or a block nested in one: a realm's alliance, a biology's parent stock
export type ReligionRegistry = Record<string, ReligionInfo>;

export type SnapshotStat = 'alliances' | 'armies' | 'books' | 'buildings' | 'cities' | 'clans'
  | 'cultures' | 'families' | 'frozen_tiles' | 'houses' | 'infected' | 'kingdoms'
  | 'languages' | 'population' | 'religions' | 'sick' | 'subspecies' | 'trees' | 'vegetation'
  | 'wars' | 'wild_creatures';

export type SubspeciesRegistry = Record<string, SubspeciesInfo>;

// The blocks carrying a chronicler-written trait summary — every tier whose traits WorldBox lets drift, plus the favorite's own.
export type TraitSummarySource = 'clan' | 'culture' | 'favorite' | 'language' | 'religion' | 'subspecies';

export type WarSideKey = 'attackers' | 'defenders'; // the two camps WB fields, named as it names them — neither is « ours » from the war's own vantage

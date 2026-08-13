import { INLINE_MARKER } from '../constants/inline-marker.constant';

import { CityInfo, ClanInfo, FamilyInfo, KingdomInfo, PersonInfo } from './world.interface';

export type ActorRect = [number, number, number, number, number]; // x, y, width, height, pivot drop from the top — a part sits where its pivot meets the anchor's.
export type ChapterOverviewPanel = 'city' | 'clan' | 'family' | 'favorite' | 'kingdom' | 'world-stats';

export type CityMetaStat = 'age' | 'attractivity' | 'book_reach' | 'buildings' | 'deaths' | 'food' | 'goods' | 'houses' | 'kills' | 'renown'
  | 'territory' | 'wealth';

export type CityRegistry = Record<string, CityInfo>;
export type ClanRegistry = Record<string, ClanInfo>;
export type CumulativeStat = 'books_burnt' | 'books_read' | 'cities_conquered' | 'cities_rebelled' | 'evolutions' | 'metamorphosis' | 'plots_succeeded';

export type DeathCause = 'acid' | 'divine' | 'drowning' | 'eaten' | 'explosion' | 'fire' | 'gravity' | 'hunger'
  | 'infection' | 'old_age' | 'other' | 'plague' | 'poison' | 'tumor' | 'water' | 'weapon';

export type FamilyRegistry = Record<string, FamilyInfo>;
export type GenderedLabel = string | { f: string; m: string }; // agrees with its subject: plain when invariable, a pair otherwise — see `LabelHelpers.gendered`
export type IconKind = 'cities' | 'clans' | 'families' | 'kingdoms' | 'persons' | 'resources' | 'species';
export type InlineMarker = (typeof INLINE_MARKER)[keyof typeof INLINE_MARKER];

// A realm's own metrics — listed in full, not extended from `CityMetaStat`: a crown has no `attractivity`, nobody migrates to a realm.
export type KingdomMetaStat = 'age' | 'boats' | 'book_reach' | 'books' | 'buildings' | 'cities' | 'culture_traits' | 'deaths' | 'food' | 'foundings' | 'goods'
  | 'houses' | 'kills' | 'renown' | 'territory' | 'wars_won' | 'wealth';

export type KingdomRegistry = Record<string, KingdomInfo>;

export type LeaderKind = 'dominant_culture' | 'dominant_language' | 'dominant_religion' | 'dominant_species' | 'dominant_subspecies'
  | 'most_dominant_village' | 'most_powerful_kingdom' | 'most_renowned_clan' | 'most_renowned_family' | 'most_renowned_person';

export type LifeStage = 'adult' | 'baby' | 'child' | 'elder' | 'teen';
export type PersonRegistry = Record<string, PersonInfo>;
export type PopulationStat = 'fed_pct' | 'food_per_capita' | 'housed_pct' | 'immortals' | 'infected' | 'renown_total' | 'sick' | 'warriors' | 'wealth_per_capita';

export type RankedStatKind = 'age' | 'armor'
  | 'army_age' | 'army_deaths' | 'army_kills' | 'army_melee' | 'army_money' | 'army_ranged' | 'army_renown'
  | 'attack_speed' | 'attractivity' | 'births' | 'boats' | 'book_reach' | 'books' | 'books_written' | 'buildings' | 'children' | 'cities' | 'critical_chance'
  | 'culture_traits' | 'damage' | 'deaths'
  | 'diplomacy' | 'equipment' | 'equipment_power' | 'fed_pct' | 'food' | 'food_per_capita' | 'foundings'
  | 'goods' | 'health' | 'housed_pct' | 'houses' | 'immortals' | 'infected' | 'intelligence' | 'kills' | 'kingdoms' | 'level' | 'lifespan' | 'loyalty'
  | 'mana' | 'members'
  | 'money' | 'population' | 'renown' | 'renown_total' | 'score_rank' | 'sick' | 'speed' | 'stamina' | 'stewardship' | 'territory' | 'traits' | 'warfare'
  | 'warriors' | 'wars_won' | 'wealth' | 'wealth_per_capita';

export type SnapshotStat = 'alliances' | 'armies' | 'boats' | 'books' | 'buildings' | 'cities' | 'clans'
  | 'cultures' | 'families' | 'frozen_tiles' | 'houses' | 'infected' | 'kingdoms'
  | 'languages' | 'population' | 'religions' | 'sick' | 'subspecies' | 'trees' | 'vegetation'
  | 'wars' | 'wild_creatures';

// WB `ClanTraitGroupLibrary` ids. `body`/`mind`/`special`/`spirit` are shared with creature traits; the other three exist for clans alone.
export type TraitGroup = 'body' | 'chaos' | 'fate' | 'harmony' | 'mind' | 'special' | 'spirit';

export type TraitGroupCounts = Partial<Record<TraitGroup, number>>; // Partial where `RarityCounts` is total: most of the seven groups stay unworn and earn no row.

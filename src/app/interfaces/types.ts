import { INLINE_MARKER } from '../constants/inline-marker.constant';

import { CityInfo, KingdomInfo, PersonInfo } from './world.interface';

// Sprite rect in its sheet, in image coords — x, y, width, height, then the pivot's drop from the top edge; a part sits where its pivot meets the anchor's.
export type ActorRect = [number, number, number, number, number];

export type ChapterOverviewPanel = 'city' | 'favorite' | 'kingdom' | 'world-stats';
export type CityMetaStat = 'age' | 'buildings' | 'deaths' | 'food' | 'goods' | 'houses' | 'kills' | 'renown' | 'territory' | 'wealth';
export type CityRegistry = Record<string, CityInfo>;
export type CumulativeStat = 'books_burnt' | 'books_read' | 'cities_conquered' | 'cities_rebelled' | 'evolutions' | 'metamorphosis' | 'plots_succeeded';

export type DeathCause = 'acid' | 'divine' | 'drowning' | 'eaten' | 'explosion' | 'fire' | 'gravity' | 'hunger'
  | 'infection' | 'old_age' | 'other' | 'plague' | 'poison' | 'tumor' | 'water' | 'weapon';

export type IconKind = 'cities' | 'kingdoms' | 'persons' | 'resources' | 'species';
export type InlineMarker = (typeof INLINE_MARKER)[keyof typeof INLINE_MARKER];

// A realm's own metrics: every city one, plus its fleet, settlement count and the score dimensions it alone carries.
export type KingdomMetaStat = 'boats' | 'book_reach' | 'cities' | 'culture_traits' | 'foundings' | 'wars_won' | CityMetaStat;

export type KingdomRegistry = Record<string, KingdomInfo>;

export type LeaderKind = 'dominant_culture' | 'dominant_language' | 'dominant_religion' | 'dominant_species' | 'dominant_subspecies'
  | 'most_populous_village' | 'most_powerful_kingdom' | 'most_renowned_clan' | 'most_renowned_family' | 'most_renowned_person';

export type LifeStage = 'adult' | 'baby' | 'child' | 'elder' | 'teen';
export type PersonRegistry = Record<string, PersonInfo>;
export type PopulationStat = 'fed_pct' | 'food_per_capita' | 'housed_pct' | 'immortals' | 'infected' | 'renown_total' | 'sick' | 'warriors' | 'wealth_per_capita';

export type RankedStatKind = 'age' | 'armor' | 'attack_speed' | 'birth_rate' | 'boats' | 'book_reach' | 'buildings' | 'children' | 'cities'
  | 'critical_chance' | 'culture_traits' | 'damage' | 'deaths' | 'diplomacy' | 'equipment_power' | 'fed_pct' | 'food' | 'food_per_capita' | 'foundings'
  | 'goods' | 'health' | 'housed_pct' | 'houses' | 'immortals' | 'infected' | 'intelligence' | 'kills' | 'level' | 'lifespan' | 'loot' | 'mana' | 'money'
  | 'population' | 'renown' | 'renown_total' | 'score_rank' | 'sick' | 'speed' | 'stamina' | 'stewardship' | 'territory' | 'warfare' | 'warriors'
  | 'wars_won' | 'wealth' | 'wealth_per_capita';

export type SnapshotStat = 'alliances' | 'armies' | 'boats' | 'books' | 'buildings' | 'cities' | 'clans'
  | 'cultures' | 'equipment' | 'families' | 'frozen_tiles' | 'houses' | 'infected' | 'kingdoms'
  | 'languages' | 'population' | 'religions' | 'sick' | 'subspecies' | 'trees' | 'vegetation'
  | 'wars' | 'wild_creatures';

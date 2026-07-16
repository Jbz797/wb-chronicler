import { INLINE_MARKER } from '../constants/inline-marker.constant';

import { KingdomInfo, PersonInfo } from './world.interface';

export type ChapterOverviewPanel = 'favorite' | 'kingdom' | 'world-stats';
export type CumulativeStat = 'books_burnt' | 'books_read' | 'cities_conquered' | 'cities_rebelled' | 'evolutions' | 'metamorphosis' | 'plots_succeeded';

export type DeathCause = 'acid' | 'divine' | 'drowning' | 'eaten' | 'explosion' | 'fire' | 'gravity' | 'hunger'
  | 'infection' | 'old_age' | 'other' | 'plague' | 'poison' | 'tumor' | 'water' | 'weapon';

export type IconKind = 'kingdoms' | 'persons' | 'resources' | 'species';
export type InlineMarker = (typeof INLINE_MARKER)[keyof typeof INLINE_MARKER];
export type KingdomMetaStat = 'age' | 'buildings' | 'cities' | 'deaths' | 'food' | 'gold' | 'goods' | 'houses' | 'kills' | 'renown' | 'territory' | 'wealth';

export type KingdomPopulationStat = 'fed_pct' | 'food_per_capita' | 'housed_pct' | 'immortals' | 'infected' | 'money' | 'nobles' | 'renown_total'
  | 'sick' | 'warriors' | 'wealth_per_capita';

export type KingdomRegistry = Record<string, KingdomInfo>;

export type LeaderKind = 'dominant_culture' | 'dominant_language' | 'dominant_religion' | 'dominant_subspecies'
  | 'most_populous_kingdom' | 'most_populous_village' | 'most_renowned_clan' | 'most_renowned_person';

export type LifeStage = 'adult' | 'baby' | 'child' | 'elder' | 'teen';

export type PersonRegistry = Record<string, PersonInfo>;

export type RankedStatKind = 'age' | 'armor' | 'attack_speed' | 'birth_rate' | 'buildings' | 'children' | 'cities' | 'critical_chance'
  | 'damage' | 'deaths' | 'diplomacy' | 'equipment_power' | 'fed_pct' | 'food' | 'food_per_capita' | 'gold' | 'goods' | 'health' | 'housed_pct' | 'houses'
  | 'immortals' | 'infected' | 'intelligence' | 'kills' | 'level'
  | 'lifespan' | 'loot' | 'mana' | 'money' | 'nobles' | 'population' | 'renown' | 'renown_total' | 'sick' | 'speed' | 'stamina' | 'stewardship'
  | 'territory' | 'warfare' | 'warriors' | 'wealth' | 'wealth_per_capita';

export type SnapshotStat = 'alliances' | 'armies' | 'books' | 'buildings' | 'cities' | 'clans'
  | 'cultures' | 'equipment' | 'families' | 'frozen_tiles' | 'houses' | 'infected' | 'kingdoms'
  | 'languages' | 'population' | 'relations' | 'religions' | 'sick' | 'subspecies' | 'trees' | 'vegetation'
  | 'wars' | 'wild_creatures';

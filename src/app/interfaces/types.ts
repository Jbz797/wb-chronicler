import { INLINE_MARKER } from '../constants/inline-marker.constant';

import { KingdomInfo, PersonInfo } from './world.interface';

export type ChapterOverviewPanel = 'favorite' | 'kingdom' | 'world-stats';
export type CumulativeStat = 'books_burnt' | 'books_read' | 'cities_conquered' | 'cities_rebelled' | 'evolutions' | 'metamorphosis' | 'plots_succeeded';

export type DeathCause = 'acid' | 'divine' | 'drowning' | 'eaten' | 'explosion' | 'fire' | 'gravity' | 'hunger'
  | 'infection' | 'old_age' | 'other' | 'plague' | 'poison' | 'tumor' | 'water' | 'weapon';

export type IconKind = 'kingdoms' | 'persons' | 'resources' | 'species';
export type InlineMarker = (typeof INLINE_MARKER)[keyof typeof INLINE_MARKER];
export type KingdomMetaStat = 'age' | 'buildings' | 'cities' | 'houses' | 'renown' | 'territory';
export type KingdomRegistry = Record<string, KingdomInfo>;

export type LeaderKind = 'dominant_culture' | 'dominant_language' | 'dominant_religion' | 'dominant_subspecies'
  | 'most_populous_kingdom' | 'most_populous_village' | 'most_renowned_clan' | 'most_renowned_person';

export type PersonRegistry = Record<string, PersonInfo>;

export type RankedStatKind = 'age' | 'armor' | 'attack_speed' | 'birth_rate' | 'buildings' | 'children' | 'cities' | 'critical_chance'
  | 'damage' | 'damage_range' | 'diplomacy' | 'equipment_power' | 'health' | 'housed_pct' | 'houses' | 'immortals' | 'infected' | 'intelligence' | 'kills' | 'level'
  | 'lifespan' | 'loot' | 'mana' | 'money' | 'nobles' | 'population' | 'renown' | 'sick' | 'speed' | 'stamina' | 'stewardship'
  | 'territory' | 'warfare' | 'warriors';

export type SnapshotStat = 'alliances' | 'armies' | 'books' | 'buildings' | 'cities' | 'clans'
  | 'cultures' | 'equipment' | 'families' | 'frozen_tiles' | 'houses' | 'infected' | 'kingdoms'
  | 'languages' | 'population' | 'relations' | 'religions' | 'subspecies' | 'trees' | 'vegetation'
  | 'wars' | 'wild_creatures';

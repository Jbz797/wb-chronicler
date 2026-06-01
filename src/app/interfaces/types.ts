import { INLINE_MARKER } from '../constants/inline-marker.constant';

import { KingdomInfo, PersonInfo } from './world.interface';

export type ChapterOverviewPanel = 'favorite' | 'kingdom' | 'world-stats';
export type CumulativeStat = 'books_read' | 'plots_succeeded';
export type DeathCause = 'eaten' | 'explosion' | 'fire' | 'hunger' | 'old_age' | 'water' | 'weapon';
export type IconKind = 'kingdoms' | 'persons' | 'resources' | 'species';
export type InlineMarker = (typeof INLINE_MARKER)[keyof typeof INLINE_MARKER];
export type KingdomRegistry = Record<string, KingdomInfo>;
export type PersonRegistry = Record<string, PersonInfo>;

export type RankedStatKind = 'age' | 'armor' | 'attack_speed' | 'birth_rate' | 'children' | 'critical_chance'
  | 'damage' | 'damage_range' | 'diplomacy' | 'health' | 'intelligence' | 'kills' | 'level'
  | 'lifespan' | 'loot' | 'mana' | 'money' | 'renown' | 'speed' | 'stamina' | 'stewardship'
  | 'warfare';

export type SnapshotStat = 'alliances' | 'armies' | 'books' | 'cities' | 'clans'
  | 'cultures' | 'equipment' | 'families' | 'frozen_tiles' | 'houses' | 'kingdoms'
  | 'languages' | 'population' | 'relations' | 'religions' | 'subspecies' | 'vegetation'
  | 'wars' | 'wild_creatures';

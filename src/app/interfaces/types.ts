export type CumulativeStat = 'books_read' | 'plots_succeeded';

export type DeathCause = 'eaten' | 'explosion' | 'fire' | 'hunger' | 'old_age'
  | 'water' | 'weapon';

export type RankedStatKind = 'armor' | 'attack_speed' | 'birth_rate' | 'critical_chance'
  | 'damage' | 'damage_range' | 'diplomacy' | 'earnings' | 'health' | 'intelligence'
  | 'kills' | 'level' | 'lifespan' | 'mana' | 'money' | 'renown' | 'speed' | 'stamina'
  | 'stewardship' | 'warfare';

export type RankedStatSnapshot = Partial<Record<'current', number>> & Record<'max' | 'rank', number>;

export type SnapshotStat = 'alliances' | 'armies' | 'books' | 'cities' | 'clans'
  | 'cultures' | 'diplomatic_relations' | 'equipment' | 'families' | 'frozen_tiles'
  | 'houses' | 'kingdoms' | 'languages' | 'population' | 'religions' | 'subspecies'
  | 'vegetation' | 'wars' | 'wild_creatures';

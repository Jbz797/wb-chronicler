export type DeathCause = 'eaten' | 'explosion' | 'fire' | 'hunger' | 'old_age'
  | 'water' | 'weapon';

export type RankedStatKind = 'armor' | 'attack_speed' | 'birth_rate' | 'critical_chance'
  | 'damage' | 'damage_range' | 'diplomacy' | 'earnings' | 'health' | 'intelligence'
  | 'kills' | 'level' | 'lifespan' | 'mana' | 'money' | 'renown' | 'speed' | 'stamina'
  | 'stewardship' | 'warfare';

export type RankedStatSnapshot = Partial<Record<'current', number>> & Record<'max' | 'rank', number>;

export type WorldStat = 'alliances' | 'armies' | 'books' | 'books_read' | 'cities'
  | 'clans' | 'creatures' | 'cultures' | 'equipment' | 'families' | 'frozen_tiles'
  | 'houses' | 'kingdoms' | 'languages' | 'plots_succeeded' | 'population'
  | 'relations' | 'religions' | 'subspecies' | 'vegetation' | 'wars';

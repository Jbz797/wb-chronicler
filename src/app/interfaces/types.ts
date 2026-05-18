export type DeathCause = 'age' | 'eaten' | 'explosion' | 'fire' | 'hunger'
  | 'water' | 'weapon';

export type RankedStatKind = 'armor' | 'attack_speed' | 'critical_chance' | 'damage'
  | 'damage_range' | 'diplomacy' | 'health' | 'intelligence' | 'level' | 'lifespan'
  | 'mana' | 'speed' | 'stamina' | 'stewardship' | 'warfare';

export type RankedStatSnapshot = Partial<Record<'current', number>> & Record<'max' | 'rank', number>;

export type WorldStat = 'alliances' | 'armies' | 'books' | 'books_read' | 'cities'
  | 'clans' | 'creatures' | 'cultures' | 'equipment' | 'families' | 'frozen_tiles'
  | 'houses' | 'kingdoms' | 'languages' | 'plots_succeeded' | 'population'
  | 'relations' | 'religions' | 'subspecies' | 'vegetation' | 'wars';

export type DeathCause = 'age' | 'eaten' | 'explosion' | 'fire' | 'hunger'
  | 'water' | 'weapon';
export type RankedStatKind = 'health' | 'mana' | 'stamina';
export type RankedStatSnapshot = Record<'current' | 'max' | 'rank', number>;
export type WorldStat = 'alliances' | 'armies' | 'books' | 'books_read' | 'cities'
  | 'clans' | 'creatures' | 'cultures' | 'equipment' | 'families' | 'frozen_tiles'
  | 'houses' | 'kingdoms' | 'languages' | 'plots_succeeded' | 'population'
  | 'relations' | 'religions' | 'subspecies' | 'vegetation' | 'wars';

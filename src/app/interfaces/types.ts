export type DeathCause = 'age' | 'eaten' | 'explosion' | 'fire' | 'hunger'
  | 'water' | 'weapon';
export type RankedStatKind = 'armor' | 'damage' | 'damage_range' | 'health' | 'mana' | 'stamina';
export type RankedStatSnapshot = Partial<Record<'current', number>> & Record<'max' | 'rank', number>;
export type WorldStat = 'alliances' | 'armies' | 'books' | 'books_read' | 'cities'
  | 'clans' | 'creatures' | 'cultures' | 'equipment' | 'families' | 'frozen_tiles'
  | 'houses' | 'kingdoms' | 'languages' | 'plots_succeeded' | 'population'
  | 'relations' | 'religions' | 'subspecies' | 'vegetation' | 'wars';

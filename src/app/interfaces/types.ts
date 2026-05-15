export type DeathCause = 'age' | 'drowning' | 'eaten' | 'explosion' | 'fire'
  | 'hunger' | 'water' | 'weapon';
export type RankedStatKind = 'health' | 'mana' | 'stamina';
export type RankedStatSnapshot = Record<'current' | 'max' | 'rank', number>;
export type WorldStat = 'alliances' | 'books' | 'cities' | 'clans' | 'creatures'
  | 'cultures' | 'deaths' | 'equipment' | 'families' | 'houses' | 'kingdoms'
  | 'languages' | 'plants' | 'population' | 'religions' | 'subspecies' | 'wars';

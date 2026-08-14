// The two shapes every tier shares: a tag's id+name pointer, and the culture/language/religion/species mix of any population.

// A minimal id + name pointer to a kingdom / city / alliance, for tags and cross-links.
export interface EntityReference { id: number; name: string }

// The living of a clan, a lineage or a biology, counted and nothing more — the roster stays behind in `<tier>/info.py <id> members`, where the chronicler reads it.
export interface MemberRoster { total: number }

// A clan, a lineage and a biology answer the same shape, served by one resolver — structural, since naming the three would reach back into `types.ts`.
export interface PeopleTier {
  members: MemberRoster;
  metadata: object; // each tier's own shape; the resolver reads it by key, so it casts rather than narrowing
  population: TierPopulation;
  ranks?: { members?: number }; // `members` is the one the resolver names; the rest it reaches by key, through the same cast
}

// A soul, not a place: 42 % of WB's actors go unnamed; `PersonTagComponent` prints `ANONYMOUS_NAME`.
export interface PersonReference { id: number; name?: string }

// Top-3 shares of a civ population per dimension (% of the whole). All optional: a tier drops the dimension it is defined by, which would read 100 %.
export interface PopulationBreakdown {
  cultures?: { name: string; pct: number }[];
  languages?: { name: string; pct: number }[];
  religions?: { name: string; pct: number }[];
  species?: { asset_id: string; pct: number }[]; // absent on a lineage: WB has species inherited, so it would restate `identity.species` at 100 %
  subspecies?: { id: number; name: string; pct: number }[]; // the one dimension carrying an id: it alone has a `[u]` tag to resolve against the registry
}

// What the living of a body say of it — the settlement block less granary, head and `total`. Only the afflictions drop at zero, a share of zero being a reading.
export interface TierPopulation {
  adults: number;
  babies: number;
  children: number; // our narrative tier, a slice of childhood — WB's own « children » verdict counts every soul below adulthood, `babies` + `children` + `teens`
  couples: number;
  elders: number;
  familyless: number;
  fed_pct: number;
  happy: number;
  housed_pct: number;
  immortals?: number;
  infected?: number;
  men: number;
  money: number;
  renown_total: number;
  sick?: number;
  teens: number;
  warriors: number;
  women: number;
}

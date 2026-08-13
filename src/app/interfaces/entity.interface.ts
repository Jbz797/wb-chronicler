// The two shapes every tier shares: a tag's id+name pointer, and the culture/language/religion/species mix of any population.

// A minimal id + name pointer to a kingdom / city / alliance, for tags and cross-links.
export interface EntityReference { id: number; name: string }

// A clan's or lineage's living, counted where they are listed — the roster itself ships in the JSON for the chronicler and never reaches the UI.
export interface MemberRoster { total: number }

// A soul, not a place: 42 % of WB's actors go unnamed; `PersonTagComponent` prints `ANONYMOUS_NAME`.
export interface PersonReference { id: number; name?: string }

// Top-3 shares of a civ population per dimension (% of the whole) — only `subspecies` is always there, the rest come and go with the tier.
export interface PopulationBreakdown {
  cultures?: { name: string; pct: number }[];
  languages?: { name: string; pct: number }[];
  religions?: { name: string; pct: number }[];
  species?: { asset_id: string; name: string; pct: number }[]; // absent on a lineage: WB has species inherited, so it would restate `identity.species` at 100 %
  subspecies: { name: string; pct: number }[];
}

// A library counted, on a town's shelves or under a culture's name. Only the total reaches the UI — each volume ships in the `books` section, for the chronicler.
export interface BookShelf { total: number }

// A minimal id + name pointer to a kingdom / city / alliance, for tags and cross-links.
export interface EntityReference { id: number; name: string }

// Gear on the racks, worn by nobody. Only the total reaches the UI — the per-rack counts and the pieces themselves ship in the JSON, for the chronicler alone.
export interface EquipmentStock { total: number }

// Hulls afloat, on a realm or on the world. Only the count rides in the chapter — `<tier>/info.py … boats` names them for the chronicler.
export interface HullCount { total: number }

// The standout lineage and souls of any body that rosters people, absent below five members — and every entry optional besides: no killer, no `kills` key.
export interface Leaders {
  families?: {
    deaths?: EntityReference;
    kills?: EntityReference;
    oldest?: EntityReference;
    population?: EntityReference;
    renown?: EntityReference;
  };
  persons?: {
    births?: PersonReference;
    children?: PersonReference;
    damage?: PersonReference;
    health?: PersonReference;
    hungriest?: PersonReference;
    intelligence?: PersonReference;
    kills?: PersonReference;
    level?: PersonReference;
    money?: PersonReference;
    oldest?: PersonReference;
    renown?: PersonReference;
    speed?: PersonReference;
    youngest?: PersonReference;
  };
}

// The living of a clan, a lineage or a biology, counted and nothing more — the roster stays behind in `<tier>/info.py <id> members`, where the chronicler reads it.
export interface MemberRoster { total: number }

// A clan, a culture, a lineage, a tongue and a biology answer the same shape, served by one resolver — structural, since naming them would reach into `types.ts`.
export interface PeopleTier {
  members?: MemberRoster; // the roster of every tier but a language, which counts…
  metadata: object; // each tier's own shape; the resolver reads it by key, so it casts rather than narrowing
  population: TierPopulation;
  ranks?: { members?: number; speakers?: number }; // the two the resolver names; the rest it reaches by key, through the same cast
  speakers?: MemberRoster; // …its speakers, WB's own word for those who answer in it
}

// A soul, not a place: 42 % of WB's actors go unnamed; `PersonTagComponent` prints `ANONYMOUS_NAME`.
export interface PersonReference { id: number; name?: string }

// Top-3 shares of a civ population per dimension (% of the whole). All optional: a tier drops the dimension it is defined by, which would read 100 %.
export interface PopulationBreakdown {
  cultures?: { id: number; name: string; pct: number }[];
  kingdoms?: { id: number; name: string; pct: number }[]; // absent on a realm, which would restate itself at 100 % — present on an alliance, which spans several
  languages?: { id: number; name: string; pct: number }[];
  religions?: { id: number; name: string; pct: number }[];
  species?: { asset_id: string; pct: number }[]; // absent on a lineage: WB has species inherited, so it would restate `identity.species` at 100 %
  subspecies?: { id: number; name: string; pct: number }[]; // the species alone goes without an id: every other dimension has a tag to resolve against a registry
}

// What the living of a body say of it, of which the panels print these — the age and sex slices stay in `<tier>/info.py <id> population`, for the chronicler.
export interface TierPopulation {
  fed_pct: number;
  housed_pct: number;
  immortals?: number;
  infected?: number;
  money: number;
  renown_total: number;
  sick?: number;
  warriors: number;
}

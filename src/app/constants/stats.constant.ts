import { CumulativeStat, DeathCause, Favorite, LeaderKind, RankedStatKind, SnapshotStat, StatConfig } from '../interfaces';

// City `RankedStatKind`s resolved from `metadata` (vs `population`) — the kingdom's minus `cities`, plus the `attractivity` only a settlement can have.
export const CITY_META_STATS = new Set<RankedStatKind>([
  'age', 'attractivity', 'book_reach', 'buildings', 'deaths', 'food', 'goods', 'houses', 'kills', 'renown', 'territory', 'wealth',
]);

// The three gauges rank on their cap, never on the live value the panel prints beside it; every other kind names its own field of the favorite's `stats`.
export const FAVORITE_GAUGE_FIELDS: Partial<Record<RankedStatKind, keyof Favorite['stats']>> = { health: 'health_max', mana: 'mana_max', stamina: 'stamina_max' };

// Kingdom `RankedStatKind`s resolved from `metadata` (vs `population`) — routes the lookup in `RankedStatComponent`.
export const KINGDOM_META_STATS = new Set<RankedStatKind>([
  'age',
  'book_reach',
  'books',
  'buildings',
  'cities',
  'culture_traits',
  'deaths',
  'food',
  'foundings',
  'goods',
  'houses',
  'kills',
  'renown',
  'territory',
  'wars_won',
  'wealth',
]);

// Ranked stats shown raw (age, `%`, per-capita, placement, loyalty) — every other one compacts to `X.X K` above 100, like the world panel.
export const NON_COMPACT_STATS = new Set<RankedStatKind>(['age', 'fed_pct', 'food_per_capita', 'housed_pct', 'loyalty', 'score_rank', 'wealth_per_capita']);

// Favorite combat stats — damage / defense / attack rhythm.
export const COMBAT_STATS: StatConfig[] = [
  { key: 'damage', label: 'ui_damage' },
  { key: 'armor', label: 'ui_armor', suffix: '%' },
  { deltaSuffix: '%', key: 'critical_chance', label: 'ui_critical', suffix: '%' },
  { key: 'attack_speed', label: 'ui_attack_speed', numberFormat: '1.0-1' }, // floors at 0.5, where the default '1.0-0' would print a bare 0
];

// Cumulative world stats — UI surfaces the delta vs previous chapter (per-chapter activity).
export const CUMULATIVE_STATS: { key: CumulativeStat; label: string }[] = [
  { key: 'cities_conquered', label: 'ui_cities_conquered' },
  { key: 'cities_rebelled', label: 'ui_cities_rebelled' },
  { key: 'books_read', label: 'ui_books_read' },
  { key: 'books_burnt', label: 'ui_books_burnt' },
  { key: 'plots_succeeded', label: 'ui_plots_succeeded' },
  { key: 'metamorphosis', label: 'ui_metamorphosis' },
  { key: 'evolutions', label: 'ui_evolutions' },
];

// Who leads on a headcount — the measure each tag's medal ranks on, in the panels' own order, the parent species ahead of the biology it holds.
export const LEADERS_BY_MEMBERS: { icon?: string; key: LeaderKind; label: string }[] = [
  { icon: 'families', key: 'largest_family', label: 'ui_lineage' },
  { icon: 'most_renowned_clan', key: 'largest_clan', label: 'ui_clan' },
  { icon: 'cultures', key: 'dominant_culture', label: 'ui_culture' },
  { icon: 'languages', key: 'dominant_language', label: 'ui_language' },
  { icon: 'religions', key: 'dominant_religion', label: 'ui_religion' },
  { icon: 'species', key: 'dominant_species', label: 'ui_species' },
  { icon: 'subspecies', key: 'dominant_subspecies', label: 'ui_subspecies' },
  { icon: 'village', key: 'largest_city', label: 'ui_city' },
  { icon: 'kingdom', key: 'largest_kingdom', label: 'ui_kingdom' },
];

// A soul answers to no headcount — its own medal ranks it on the level it has earned.
export const LEADERS_BY_LEVEL: { icon?: string; key: LeaderKind; label: string }[] = [{ icon: 'person', key: 'highest_level_person', label: 'ui_nobody' }];

// The two tiers WB weighs on a composite score — eleven dimensions apiece, where a headcount is only one of them.
export const LEADERS_BY_SCORE: { icon?: string; key: LeaderKind; label: string }[] = [
  { icon: 'village', key: 'most_dominant_village', label: 'ui_city' },
  { icon: 'kingdom', key: 'most_powerful_kingdom', label: 'ui_kingdom' },
];

// The one family a settlement/realm panel names in its « Palmarès », out of the five `leaders.families` rankings Python emits.
export const LEADER_FAMILY_ROWS: { icon: string; key: 'population'; label: string }[] = [
  { icon: 'assets/img/world/families.png', key: 'population', label: 'ui_leading_family' },
];

// The souls a settlement/realm panel names, out of all the `leaders.persons` rankings: fame, power, violence, fortune, age.
export const LEADER_PERSON_ROWS: { icon: string; key: 'kills' | 'level' | 'money' | 'oldest' | 'renown'; label: string }[] = [
  { icon: 'assets/img/world/most_renowned_person.png', key: 'renown', label: 'ui_most_renowned' },
  { icon: 'assets/img/stats/level.png', key: 'level', label: 'ui_highest_level' },
  { icon: 'assets/img/stats/kills.png', key: 'kills', label: 'ui_deadliest' },
  { icon: 'assets/img/stats/money.png', key: 'money', label: 'ui_wealthiest' },
  { icon: 'assets/img/stats/age.png', key: 'oldest', label: 'ui_eldest' },
];

// Death causes — runtime-sorted by per-chapter count desc and 0-count rows hidden in `world-stats.component`. Icons at `assets/img/world/deaths/<key>.png`.
export const DEATH_CAUSES: { key: DeathCause; label: string }[] = [
  { key: 'acid', label: 'ui_acid' },
  { key: 'divine', label: 'ui_divine' },
  { key: 'drowning', label: 'ui_drowning' },
  { key: 'eaten', label: 'ui_eaten' },
  { key: 'explosion', label: 'ui_blast' },
  { key: 'fire', label: 'ui_fire' },
  { key: 'gravity', label: 'ui_gravity' },
  { key: 'hunger', label: 'ui_hunger' },
  { key: 'infection', label: 'ui_infection' },
  { key: 'old_age', label: 'ui_old_age' },
  { key: 'other', label: 'ui_others' },
  { key: 'plague', label: 'ui_plague' },
  { key: 'poison', label: 'ui_poison' },
  { key: 'tumor', label: 'ui_tumor' },
  { key: 'water', label: 'ui_water' },
  { key: 'weapon', label: 'ui_strife' },
];

// Favorite social skills — diplomacy / military / governance / intellect.
export const SKILL_STATS: StatConfig[] = [
  { key: 'diplomacy', label: 'ui_diplomacy' },
  { key: 'warfare', label: 'ui_warfare' },
  { key: 'stewardship', label: 'ui_stewardship' },
  { key: 'intelligence', label: 'ui_intelligence' },
];

// Snapshot world stats — display order: demography → environment → society → conflict → culture → activity. `hideIfZero` hides outbreak-style rows when idle.
export const SNAPSHOT_STATS: { hideIfZero?: boolean; key: SnapshotStat; label: string }[] = [
  { key: 'population', label: 'ui_sapient_population' },
  { hideIfZero: true, key: 'sick', label: 'ui_sick' },
  { hideIfZero: true, key: 'infected', label: 'ui_infected' },
  { key: 'wild_creatures', label: 'ui_creatures' },
  { key: 'subspecies', label: 'ui_subspecies_count' },
  { key: 'trees', label: 'ui_trees' },
  { key: 'vegetation', label: 'ui_other_vegetation' },
  { key: 'frozen_tiles', label: 'ui_frozen_tiles' },
  { key: 'kingdoms', label: 'ui_kingdoms' },
  { key: 'cities', label: 'ui_cities' },
  { key: 'buildings', label: 'ui_buildings' },
  { key: 'houses', label: 'ui_houses' },
  { key: 'families', label: 'ui_families' },
  { key: 'clans', label: 'ui_clans' },
  { key: 'alliances', label: 'ui_alliances' },
  { hideIfZero: true, key: 'wars', label: 'ui_wars' },
  { key: 'armies', label: 'ui_armies' },
  { key: 'languages', label: 'ui_languages' },
  { key: 'cultures', label: 'ui_cultures' },
  { key: 'religions', label: 'ui_religions' },
  { key: 'books', label: 'ui_books' },
];

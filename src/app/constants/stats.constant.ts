import { CumulativeStat, DeathCause, Favorite, LeaderGroupConfig, LeaderMeasure, RankedStatKind, SnapshotStat, StatConfig } from '../interfaces';

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
  { icon: 'damage', key: 'damage_max', label: 'ui_damage' },
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

// The one family a settlement/realm panel names in its « Palmarès », out of the five `leaders.families` rankings Python emits.
export const LEADER_FAMILY_ROWS: { icon: string; key: 'population'; label: string }[] = [
  { icon: 'assets/img/world/families.png', key: 'population', label: 'ui_leading_family' },
];

// The world « Palmarès », one table per group: a soul's level and skills first (in `SKILL_STATS` order), then the parent species ahead of the biology it holds.
export const LEADER_GROUPS: LeaderGroupConfig[] = [
  { group: 'persons', label: 'ui_persons', measures: ['level', 'diplomacy', 'warfare', 'stewardship', 'intelligence'] },
  { group: 'species', label: 'ui_species_plural', measures: ['population'] },
  { group: 'subspecies', label: 'ui_subspecies_count', measures: ['population'] },
  { group: 'families', label: 'ui_families', measures: ['population'] },
  { group: 'clans', label: 'ui_clans', measures: ['population'] },
  { group: 'cultures', label: 'ui_cultures', measures: ['population'] },
  { group: 'languages', label: 'ui_languages', measures: ['population'] },
  { group: 'religions', label: 'ui_religions', measures: ['population'] },
  { group: 'cities', label: 'ui_cities', measures: ['population', 'score'] },
  { group: 'kingdoms', label: 'ui_kingdoms', measures: ['population', 'score'] },
];

// Each world record's sprite and label — `score`, the composite WB weighs a town and a crown on, under the label the city and kingdom panels print.
export const LEADER_MEASURES: Record<LeaderMeasure, { icon: string; label: string }> = {
  diplomacy: { icon: 'assets/img/stats/diplomacy.png', label: 'ui_diplomacy' },
  intelligence: { icon: 'assets/img/stats/intelligence.png', label: 'ui_intelligence' },
  level: { icon: 'assets/img/stats/level.png', label: 'ui_level' },
  population: { icon: 'assets/img/world/population.png', label: 'ui_population' },
  score: { icon: 'assets/img/podium/1.png', label: 'ui_score' },
  stewardship: { icon: 'assets/img/stats/stewardship.png', label: 'ui_stewardship' },
  warfare: { icon: 'assets/img/stats/warfare.png', label: 'ui_warfare' },
};

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
// `icon` names the sprite in `assets/img/world/`, filed by concept: `population.png` draws a crowd, whichever crowd the key happens to count.
export const SNAPSHOT_STATS: { hideIfZero?: boolean; icon?: string; key: SnapshotStat; label: string }[] = [
  { icon: 'population', key: 'sapient_population', label: 'ui_sapient_population' },
  { hideIfZero: true, key: 'sick', label: 'ui_sick' },
  { hideIfZero: true, key: 'infected', label: 'ui_infected' },
  { key: 'wild_creatures', label: 'ui_creatures' },
  { key: 'subspecies', label: 'ui_subspecies_count' },
  { key: 'trees', label: 'ui_trees' },
  { key: 'vegetation', label: 'ui_other_vegetation' },
  { hideIfZero: true, key: 'frozen_tiles', label: 'ui_frozen_tiles' },
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

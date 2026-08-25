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
export const NON_COMPACT_STATS = new Set<RankedStatKind>([
  'age', 'fed_pct', 'food_per_capita', 'housed_pct', 'loyalty', 'score_rank', 'wealth_per_capita',
]);

// Favorite combat stats — damage / defense / attack rhythm.
export const COMBAT_STATS: StatConfig[] = [
  { key: 'damage', label: 'Dommages' },
  { key: 'armor', label: 'Armure', suffix: '%' },
  { deltaSuffix: '%', key: 'critical_chance', label: 'Critiques', suffix: '%' },
  { key: 'attack_speed', label: 'Cadence' },
];

// Cumulative world stats — UI surfaces the delta vs previous chapter (per-chapter activity).
export const CUMULATIVE_STATS: { key: CumulativeStat; label: string }[] = [
  { key: 'cities_conquered', label: 'Villes conquises' },
  { key: 'cities_rebelled', label: 'Villes révoltées' },
  { key: 'books_read', label: 'Livres lus' },
  { key: 'books_burnt', label: 'Livres brûlés' },
  { key: 'plots_succeeded', label: 'Complots réussis' },
  { key: 'metamorphosis', label: 'Métamorphoses' },
  { key: 'evolutions', label: 'Évolutions' },
];

// Who leads on a headcount — the measure each tag's medal ranks on, in the panels' own order, the parent species ahead of the biology it holds.
export const LEADERS_BY_MEMBERS: { icon?: string; key: LeaderKind; label: string }[] = [
  { icon: 'families', key: 'largest_family', label: 'Lignée' },
  { icon: 'most_renowned_clan', key: 'largest_clan', label: 'Clan' },
  { icon: 'cultures', key: 'dominant_culture', label: 'Culture' },
  { icon: 'languages', key: 'dominant_language', label: 'Langue' },
  { icon: 'religions', key: 'dominant_religion', label: 'Religion' },
  { icon: 'species', key: 'dominant_species', label: 'Espèce' },
  { icon: 'subspecies', key: 'dominant_subspecies', label: 'Sous-espèce' },
  { icon: 'village', key: 'largest_city', label: 'Cité' },
  { icon: 'kingdom', key: 'largest_kingdom', label: 'Royaume' },
];

// A soul answers to no headcount — its own medal ranks it on the level it has earned.
export const LEADERS_BY_LEVEL: { icon?: string; key: LeaderKind; label: string }[] = [{ icon: 'person', key: 'highest_level_person', label: 'Personne' }];

// The two tiers WB weighs on a composite score — eleven dimensions apiece, where a headcount is only one of them.
export const LEADERS_BY_SCORE: { icon?: string; key: LeaderKind; label: string }[] = [
  { icon: 'village', key: 'most_dominant_village', label: 'Cité' },
  { icon: 'kingdom', key: 'most_powerful_kingdom', label: 'Royaume' },
];

// The one family a settlement/realm panel names in its « Palmarès », out of the five `leaders.families` rankings Python emits.
export const LEADER_FAMILY_ROWS: { icon: string; key: 'population'; label: string }[] = [
  { icon: 'assets/img/world/families.png', key: 'population', label: 'Famille dominante' },
];

// The souls a settlement/realm panel names, out of all the `leaders.persons` rankings: fame, power, violence, fortune, age.
export const LEADER_PERSON_ROWS: { icon: string; key: 'kills' | 'level' | 'money' | 'oldest' | 'renown'; label: string }[] = [
  { icon: 'assets/img/world/most_renowned_person.png', key: 'renown', label: 'Illustre' },
  { icon: 'assets/img/stats/level.png', key: 'level', label: 'Plus haut niveau' },
  { icon: 'assets/img/stats/kills.png', key: 'kills', label: 'Plus meurtrier' },
  { icon: 'assets/img/stats/money.png', key: 'money', label: 'Plus riche' },
  { icon: 'assets/img/stats/age.png', key: 'oldest', label: 'Doyen' },
];

// Death causes — runtime-sorted by per-chapter count desc and 0-count rows hidden in `world-stats.component`. Icons at `assets/img/world/deaths/<key>.png`.
export const DEATH_CAUSES: { key: DeathCause; label: string }[] = [
  { key: 'acid', label: 'Acide' },
  { key: 'divine', label: 'Divine' },
  { key: 'drowning', label: 'Noyade' },
  { key: 'eaten', label: 'Dévorés' },
  { key: 'explosion', label: 'Explosion' },
  { key: 'fire', label: 'Feu' },
  { key: 'gravity', label: 'Gravité' },
  { key: 'hunger', label: 'Faim' },
  { key: 'infection', label: 'Infection' },
  { key: 'old_age', label: 'Naturelle' },
  { key: 'other', label: 'Autres' },
  { key: 'plague', label: 'Peste' },
  { key: 'poison', label: 'Poison' },
  { key: 'tumor', label: 'Tumeur' },
  { key: 'water', label: 'Eau' },
  { key: 'weapon', label: 'Conflit' },
];

// Favorite social skills — diplomacy / military / governance / intellect.
export const SKILL_STATS: StatConfig[] = [
  { key: 'diplomacy', label: 'Diplomatie' },
  { key: 'warfare', label: 'Martial' },
  { key: 'stewardship', label: 'Intendance' },
  { key: 'intelligence', label: 'Intelligence' },
];

// Snapshot world stats — display order: demography → environment → society → conflict → culture → activity. `hideIfZero` hides outbreak-style rows when idle.
export const SNAPSHOT_STATS: { hideIfZero?: boolean; key: SnapshotStat; label: string }[] = [
  { key: 'population', label: 'Population pensante' },
  { hideIfZero: true, key: 'sick', label: 'Malades' },
  { hideIfZero: true, key: 'infected', label: 'Infectés' },
  { key: 'wild_creatures', label: 'Créatures' },
  { key: 'subspecies', label: 'Sous-espèces' },
  { key: 'trees', label: 'Arbres' },
  { key: 'vegetation', label: 'Autre végétation' },
  { key: 'frozen_tiles', label: 'Tuiles gelées' },
  { key: 'kingdoms', label: 'Royaumes' },
  { key: 'cities', label: 'Cités' },
  { key: 'buildings', label: 'Bâtiments' },
  { key: 'houses', label: 'Maisons' },
  { key: 'families', label: 'Familles' },
  { key: 'clans', label: 'Clans' },
  { key: 'alliances', label: 'Alliances' },
  { hideIfZero: true, key: 'wars', label: 'Guerres' },
  { key: 'armies', label: 'Armées' },
  { key: 'languages', label: 'Langues' },
  { key: 'cultures', label: 'Cultures' },
  { key: 'religions', label: 'Religions' },
  { key: 'books', label: 'Livres' },
];

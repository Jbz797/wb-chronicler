import { CumulativeStat, DeathCause, GenderedLabel, LeaderKind, LifeStage, RankedStatKind, SnapshotStat, StatConfig, TraitGroup } from '../interfaces';

export const ANONYMOUS_NAME = 'Anonyme'; // Stands in for a person WB never named — 42 % of its actors — so the row holds instead of showing a mute plate.

// French labels for `plot.type_id` — sourced from WB's `PlotsLibrary`. Unknown ids fall back to the raw id at render time.
export const PLOT_TYPE_LABELS: Readonly<Record<string, string>> = {
  alliance_create: "Création d'alliance",
  alliance_destroy: "Destruction d'alliance",
  alliance_join: 'Rejoindre une alliance',
  attacker_stop_war: 'Cessez-le-feu',
  big_cast_bubble_shield: 'Bouclier de bulles',
  big_cast_coffee: 'Rite du café',
  big_cast_madness: 'Rite de folie',
  big_cast_slowness: 'Rite de lenteur',
  cause_rebellion: 'Provocation de rébellion',
  clan_ascension: 'Ascension de clan',
  culture_divide: 'Schisme culturel',
  language_divergence: 'Divergence linguistique',
  new_book: "Écriture d'un livre",
  new_culture: 'Création de culture',
  new_language: 'Création de langue',
  new_religion: 'Création de religion',
  new_war: 'Déclaration de guerre',
  rebellion: 'Rébellion',
  religion_schism: 'Schisme religieux',
  summon_angles: "Invocation d'anges",
  summon_demons: 'Invocation de démons',
  summon_earthquake: "Invocation d'un séisme",
  summon_hellstorm: "Invocation d'une tempête infernale",
  summon_living_plants: 'Invocation de plantes vivantes',
  summon_meteor_rain: 'Invocation de météores',
  summon_skeletons: 'Invocation de squelettes',
  summon_stormfront: "Invocation d'une tempête",
  summon_thunderstorm: "Invocation d'un orage",
};

// French labels for `metadata.life_stage` — WB age tiers (baby → elder), shown lowercase next to the age.
export const LIFE_STAGE_LABELS: Readonly<Record<LifeStage, GenderedLabel>> = {
  adult: 'adulte',
  baby: 'bébé',
  child: 'enfant',
  elder: { f: 'aînée', m: 'aîné' },
  teen: { f: 'adolescente', m: 'adolescent' },
};

// The favorite's two attachments — each agrees with the companion's own sex, not the favorite's.
export const COMPANION_LABELS: Readonly<Record<string, GenderedLabel>> = {
  best_friend: { f: 'Meilleure amie', m: 'Meilleur ami' },
  lover: { f: 'Amoureuse', m: 'Amoureux' },
};

// French labels for `metadata.personality` (mirrors the IDs WB stores). `null` means commoner (no role).
export const PERSONALITY_LABELS: Readonly<Record<string, GenderedLabel>> = {
  administrator: { f: 'Administratrice', m: 'Administrateur' },
  balanced: { f: 'Équilibrée', m: 'Équilibré' },
  diplomat: 'Diplomate',
  militarist: 'Militariste',
  wildcard: 'Imprévisible',
};

// French labels for `metadata.tenure_years` — names the post the years are counted for. Only these professions hold one.
export const TENURE_LABELS: Readonly<Record<string, string>> = { army_captain: 'Commandement', king: 'Règne', leader: 'Direction' };

// The seven buckets WB sorts clan traits into (`ClanTraitGroupLibrary`). Ours: the game ships no locale for the four it invented for clans.
export const TRAIT_GROUP_LABELS: Readonly<Record<TraitGroup, string>> = {
  body: 'Corps', chaos: 'Chaos', fate: 'Destin', harmony: 'Harmonie', mind: 'Mental', special: 'Spécial', spirit: 'Esprit',
};

// French labels for `metadata.roles` (active = current position, !active = historical foundation) — Python emits the canonical order, do not re-sort here.
export const ROLE_LABELS: Readonly<Record<string, { active: boolean; label: GenderedLabel }>> = {
  alliance_founder: { active: false, label: { f: "Fondatrice d'alliance", m: "Fondateur d'alliance" } },
  clan_chief: { active: true, label: { f: 'Cheffe de clan', m: 'Chef de clan' } },
  clan_founder: { active: false, label: { f: 'Fondatrice de clan', m: 'Fondateur de clan' } },
  culture_creator: { active: false, label: { f: 'Créatrice de culture', m: 'Créateur de culture' } },
  family_alpha: { active: true, label: { f: 'Cheffe de famille', m: 'Chef de famille' } },
  family_founder: { active: false, label: { f: 'Fondatrice de famille', m: 'Fondateur de famille' } },
  language_creator: { active: false, label: { f: 'Créatrice de langue', m: 'Créateur de langue' } },
  religion_creator: { active: false, label: { f: 'Créatrice de religion', m: 'Créateur de religion' } },
  village_founder: { active: false, label: { f: 'Fondatrice de village', m: 'Fondateur de village' } },
};

// City `RankedStatKind`s resolved from `metadata` (vs `population`) — the kingdom's minus `cities`, plus the `attractivity` only a settlement can have.
export const CITY_META_STATS = new Set<RankedStatKind>([
  'age', 'attractivity', 'book_reach', 'buildings', 'deaths', 'food', 'goods', 'houses', 'kills', 'renown', 'territory', 'wealth',
]);

// Kingdom `RankedStatKind`s resolved from `metadata` (vs `population`) — routes the lookup in `RankedStatComponent`.
export const KINGDOM_META_STATS = new Set<RankedStatKind>([
  'age',
  'boats',
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

// Ranked stats shown raw (age, `%`, per-capita, placement, loyalty) — every other kingdom/city/alliance stat compacts to `X.X K` above 100, like the world panel.
export const NON_COMPACT_STATS = new Set<RankedStatKind>(['age', 'fed_pct', 'food_per_capita', 'housed_pct', 'loyalty', 'score_rank', 'wealth_per_capita']);

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

// Top entity per category (WB « Records »). Ordered like the collapses (person → village → kingdom); `icon` overrides the `<key>.png` lookup for `dominant_*`.
export const LEADERS: { icon?: string; key: LeaderKind; label: string }[] = [
  { icon: 'person', key: 'most_renowned_person', label: 'P. illustre' },
  { icon: 'village', key: 'most_dominant_village', label: 'V. dominant' },
  { icon: 'kingdom', key: 'most_powerful_kingdom', label: 'R. dominant' },
  { key: 'most_renowned_clan', label: 'C. illustre' },
  { icon: 'families', key: 'most_renowned_family', label: 'F. illustre' },
  { icon: 'species', key: 'dominant_species', label: 'Espèce' },
  { icon: 'cultures', key: 'dominant_culture', label: 'Culture' },
  { icon: 'languages', key: 'dominant_language', label: 'Langue' },
  { icon: 'religions', key: 'dominant_religion', label: 'Religion' },
  { icon: 'subspecies', key: 'dominant_subspecies', label: 'S. espèce' },
];

// The one family a settlement/realm panel names in its « Palmarès », out of the five `leaders.families` rankings Python emits.
export const LEADER_FAMILY_ROWS: { icon: string; key: 'population'; label: string }[] = [
  { icon: 'assets/img/world/families.png', key: 'population', label: 'Famille dominante' },
];

// The five souls a settlement/realm panel names, out of the thirteen `leaders.persons` rankings: fame, power, violence, fortune, age.
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

// French labels for kingdom diplomatic relation statuses (ally / enemy / neutral) — mirrors WB's runtime relation state derived from alliances + ongoing wars.
export const RELATION_STATUS_LABELS = { ally: 'Allié', enemy: 'Ennemi', neutral: 'Neutre' } as const;

// ng-zorro nz-tag colors per relation status — green for allies, red for active enemies, default for everything else.
export const RELATION_STATUS_NZ_COLORS = { ally: 'green', enemy: 'red', neutral: 'default' } as const;

// French labels for `war.war_type` — sourced from WB's `meta_wars` locale (war_type_*).
export const WAR_TYPE_LABELS = { conquest: 'Conquête', inspire: 'Inspirée', rebellion: 'Rébellion', spite: 'Dépit', whisper: 'Murmure' } as const;

// Snapshot world stats — display order: demography → environment → society → conflict → culture → activity. `hideIfZero` hides outbreak-style rows when idle.
export const SNAPSHOT_STATS: { hideIfZero?: boolean; key: SnapshotStat; label: string }[] = [
  { key: 'population', label: 'Population pensante' },
  { hideIfZero: true, key: 'sick', label: 'Malades' },
  { hideIfZero: true, key: 'infected', label: 'Infectés' },
  { key: 'wild_creatures', label: 'Créatures' },
  { key: 'subspecies', label: 'Sous-espèces' },
  { key: 'vegetation', label: 'Végétation' },
  { key: 'trees', label: 'Arbres' },
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
  { hideIfZero: true, key: 'boats', label: 'Bateaux' },
  { key: 'languages', label: 'Langues' },
  { key: 'cultures', label: 'Cultures' },
  { key: 'religions', label: 'Religions' },
  { key: 'books', label: 'Livres' },
];

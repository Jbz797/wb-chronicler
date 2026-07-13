import { CumulativeStat, DeathCause, LeaderKind, LifeStage, RankedStatKind, SnapshotStat, StatConfig } from '../interfaces';

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
export const LIFE_STAGE_LABELS: Readonly<Record<LifeStage, string>> = {
  adult: 'adulte',
  baby: 'bébé',
  child: 'enfant',
  elder: 'aîné',
  teen: 'adolescent',
};

// French labels for `metadata.personality` (mirrors the IDs WB stores). `null` means commoner (no role).
export const PERSONALITY_LABELS: Readonly<Record<string, string>> = {
  administrator: 'Administrateur',
  balanced: 'Équilibré',
  diplomat: 'Diplomate',
  militarist: 'Militariste',
  wildcard: 'Imprévisible',
};

// French labels for `metadata.profession` — mapped from the save's int field (2=unit, 3=king, 4=leader, 5=warrior).
export const PROFESSION_LABELS: Readonly<Record<string, string>> = {
  army_captain: "Capitaine d'armée",
  king: 'Roi',
  leader: 'Chef de village',
  unit: 'Civil',
  warrior: 'Guerrier',
};

// French labels for `metadata.roles` (active = current position, !active = historical foundation) — Python emits the canonical order, do not re-sort here.
export const ROLE_LABELS: Readonly<Record<string, { active: boolean; label: string }>> = {
  alliance_founder: { active: false, label: "Fondateur d'alliance" },
  army_captain: { active: true, label: "Capitaine d'armée" },
  clan_chief: { active: true, label: 'Chef de clan' },
  clan_founder: { active: false, label: 'Fondateur de clan' },
  culture_creator: { active: false, label: 'Créateur de culture' },
  family_alpha: { active: true, label: 'Chef de famille' },
  family_founder: { active: false, label: 'Fondateur de famille' },
  language_creator: { active: false, label: 'Créateur de langue' },
  religion_creator: { active: false, label: 'Créateur de religion' },
  village_founder: { active: false, label: 'Fondateur de village' },
};

// Kingdom `RankedStatKind`s resolved from `metadata` (vs `population`) — routes the lookup in `RankedStatComponent`.
export const KINGDOM_META_STATS = new Set<RankedStatKind>(['age', 'buildings', 'cities', 'food', 'gold', 'goods', 'houses', 'renown', 'territory']);

// Kingdom ranked stats shown raw (age in years, `%`, per-capita ratio) — every other kingdom stat compacts to `X.X K` above 100, like the world panel.
export const NON_COMPACT_KINGDOM_STATS = new Set<RankedStatKind>(['age', 'fed_pct', 'food_per_capita', 'housed_pct']);

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

// Top entity per category (mirrors WB's « Records » panel). `icon` overrides the default `<key>.png` lookup so `dominant_*` reuses the snapshot icons.
export const LEADERS: { icon?: string; key: LeaderKind; label: string }[] = [
  { key: 'most_populous_village', label: 'Village peuplé' },
  { key: 'most_populous_kingdom', label: 'Roy. peuplé' },
  { key: 'most_renowned_person', label: 'Perso. illustre' },
  { key: 'most_renowned_clan', label: 'Clan illustre' },
  { icon: 'cultures', key: 'dominant_culture', label: 'Culture' },
  { icon: 'languages', key: 'dominant_language', label: 'Langue' },
  { icon: 'religions', key: 'dominant_religion', label: 'Religion' },
  { icon: 'subspecies', key: 'dominant_subspecies', label: 'Sous-espèce' },
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
export const RELATION_STATUS_LABELS = {
  ally: 'Allié',
  enemy: 'Ennemi',
  neutral: 'Neutre',
} as const;

// ng-zorro nz-tag colors per relation status — green for allies, red for active enemies, default for everything else.
export const RELATION_STATUS_NZ_COLORS = {
  ally: 'green',
  enemy: 'red',
  neutral: 'default',
} as const;

// French labels for `war.war_type` — sourced from WB's `meta_wars` locale (war_type_*).
export const WAR_TYPE_LABELS = {
  conquest: 'Conquête',
  inspire: 'Inspirée',
  rebellion: 'Rébellion',
  spite: 'Dépit',
  whisper: 'Murmure',
} as const;

// Snapshot world stats — display order: demography → environment → society → conflict → culture → activity. `hideIfZero` hides outbreak-style rows when idle.
export const SNAPSHOT_STATS: { hideIfZero?: boolean; key: SnapshotStat; label: string }[] = [
  { key: 'population', label: 'Population pensante' },
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
  { key: 'wars', label: 'Guerres' },
  { key: 'armies', label: 'Armées' },
  { key: 'languages', label: 'Langues' },
  { key: 'cultures', label: 'Cultures' },
  { key: 'religions', label: 'Religions' },
  { key: 'equipment', label: 'Équipement' },
  { key: 'books', label: 'Livres' },
];

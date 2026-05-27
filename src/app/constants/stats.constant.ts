import { CumulativeStat, DeathCause, SnapshotStat, StatConfig } from '../interfaces';

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

// Favorite combat stats — damage / defense / attack rhythm.
export const COMBAT_STATS: StatConfig[] = [
  { key: 'damage', label: 'Dommages' },
  { key: 'damage_range', label: 'Aléa', numberFormat: '1.1-1', showRank: false },
  { key: 'armor', label: 'Armure', suffix: '%' },
  { deltaSuffix: '%', key: 'critical_chance', label: 'Critiques', suffix: '%' },
  { key: 'attack_speed', label: 'Cadence' },
];

// Cumulative world stats — UI surfaces the delta vs previous chapter (per-chapter activity).
export const CUMULATIVE_STATS: { key: CumulativeStat; label: string }[] = [
  { key: 'books_read', label: 'Livres lus' },
  { key: 'plots_succeeded', label: 'Complots réussis' },
];

// Death causes — display order by descending magnitude on current save (most-frequent first).
export const DEATH_CAUSES: { key: DeathCause; label: string }[] = [
  { key: 'weapon', label: 'Armes' },
  { key: 'old_age', label: 'Âge' },
  { key: 'eaten', label: 'Dévorés' },
  { key: 'fire', label: 'Feu' },
  { key: 'water', label: 'Eau' },
  { key: 'explosion', label: 'Explosion' },
  { key: 'hunger', label: 'Faim' },
];

// Favorite social skills — diplomacy / military / governance / intellect.
export const SKILL_STATS: StatConfig[] = [
  { key: 'diplomacy', label: 'Diplomatie' },
  { key: 'warfare', label: 'Martial' },
  { key: 'stewardship', label: 'Intendance' },
  { key: 'intelligence', label: 'Intelligence' },
];

// Snapshot world stats — display order: demography → environment → society → conflict → culture → activity.
export const SNAPSHOT_STATS: { key: SnapshotStat; label: string }[] = [
  { key: 'population', label: 'Population' },
  { key: 'wild_creatures', label: 'Créatures' },
  { key: 'subspecies', label: 'Sous-espèces' },
  { key: 'vegetation', label: 'Végétation' },
  { key: 'frozen_tiles', label: 'Tuiles gelées' },
  { key: 'houses', label: 'Maisons' },
  { key: 'kingdoms', label: 'Royaumes' },
  { key: 'cities', label: 'Villes' },
  { key: 'clans', label: 'Clans' },
  { key: 'families', label: 'Familles' },
  { key: 'relations', label: 'Relations' },
  { key: 'alliances', label: 'Alliances' },
  { key: 'wars', label: 'Guerres' },
  { key: 'armies', label: 'Armées' },
  { key: 'languages', label: 'Langues' },
  { key: 'cultures', label: 'Cultures' },
  { key: 'religions', label: 'Religions' },
  { key: 'equipment', label: 'Équipement' },
  { key: 'books', label: 'Livres' },
];

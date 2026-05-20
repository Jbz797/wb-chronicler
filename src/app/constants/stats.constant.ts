import { CumulativeStat, DeathCause, RankedStatKind, SnapshotStat } from '../interfaces';

// Favorite combat stats — damage / defense / attack rhythm.
export const COMBAT_STATS: { key: RankedStatKind; label: string }[] = [
  { key: 'damage', label: 'Dommages' },
  { key: 'damage_range', label: 'Aléa' },
  { key: 'armor', label: 'Armure' },
  { key: 'critical_chance', label: 'Critiques' },
  { key: 'attack_speed', label: 'Cadence' },
];

// Cumulative world stats — UI surfaces the delta vs previous chapter (per-chapter activity).
export const CUMULATIVE_STATS: { key: CumulativeStat; label: string }[] = [
  { key: 'plots_succeeded', label: 'Complots réussis' },
  { key: 'books_read', label: 'Livres lus' },
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
export const SKILL_STATS: { key: RankedStatKind; label: string }[] = [
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

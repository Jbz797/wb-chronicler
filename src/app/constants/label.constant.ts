import { GenderedLabel, LifeStage, TraitGroup } from '../interfaces';

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

// French labels for kingdom diplomatic relation statuses (ally / enemy / neutral) — mirrors WB's runtime relation state derived from alliances + ongoing wars.
export const RELATION_STATUS_LABELS = { ally: 'Allié', enemy: 'Ennemi', neutral: 'Neutre' } as const;

// ng-zorro nz-tag colors per relation status — green for allies, red for active enemies, default for everything else.
export const RELATION_STATUS_NZ_COLORS = { ally: 'green', enemy: 'red', neutral: 'default' } as const;

// French labels for `war.war_type` — sourced from WB's `meta_wars` locale (war_type_*).
export const WAR_TYPE_LABELS = { conquest: 'Conquête', inspire: 'Inspirée', rebellion: 'Rébellion', spite: 'Dépit', whisper: 'Murmure' } as const;

// WB's 29 biomes, French label per key — fixed vocabulary, so it lives here, not in `biomes.json`. Python emits the key alone; an unknown one falls through.
export const BIOME_NAMES: Readonly<Record<string, string>> = {
  biomass: 'Biomasse',
  birch: 'Bouleau',
  candy: 'Bonbons',
  celestial: 'Céleste',
  clover: 'Trèfle',
  corrupted: 'Corrompu',
  crystal: 'Cristal',
  cybercore: 'Cybercore',
  desert: 'Désert',
  enchanted: 'Enchanté',
  flower: 'Fleur',
  garlic: 'Ail',
  grass: 'Herbe',
  hills: 'Collines',
  infernal: 'Infernal',
  jungle: 'Jungle',
  lemon: 'Citron',
  maple: 'Érable',
  mushroom: 'Champignon',
  paradox: 'Paradoxe',
  permafrost: 'Permafrost',
  rocklands: 'Terres rocheuses',
  sand: 'Sable',
  savanna: 'Savane',
  singularity_swamp: 'Marais de singularité',
  super_pumpkin: 'Super Citrouille',
  swamp: 'Marais',
  tumor: 'Tumeur',
  wasteland: 'Terre dévastée',
};

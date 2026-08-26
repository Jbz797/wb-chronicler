import { GenderedLabel, LifeStage } from '../interfaces';

export const ANONYMOUS_NAME = 'Anonyme'; // Stands in for a person WB never named — 42 % of its actors — so the row holds instead of showing a mute plate.

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

// The favorite's two attachments — each agrees with the companion's own sex, not the favorite's.
export const COMPANION_LABELS: Readonly<Record<string, GenderedLabel>> = {
  best_friend: { f: 'Meilleure amie', m: 'Meilleur ami' },
  lover: { f: 'Amoureuse', m: 'Amoureux' },
};

// French labels for `metadata.life_stage` — WB age tiers (baby → elder), shown lowercase next to the age.
export const LIFE_STAGE_LABELS: Readonly<Record<LifeStage, GenderedLabel>> = {
  adult: 'adulte',
  baby: 'bébé',
  child: 'enfant',
  elder: { f: 'aînée', m: 'aîné' },
  teen: { f: 'adolescente', m: 'adolescent' },
};

// French labels for `metadata.personality` (mirrors the IDs WB stores). `null` means commoner (no role).
export const PERSONALITY_LABELS: Readonly<Record<string, GenderedLabel>> = {
  administrator: { f: 'Administratrice', m: 'Administrateur' },
  balanced: { f: 'Équilibrée', m: 'Équilibré' },
  diplomat: 'Diplomate',
  militarist: 'Militariste',
  wildcard: 'Imprévisible',
};

// French labels for `chapter.json.tags`, whose meaning `history/tags.md` spells out for the chronicler. Unknown codes fall back to the raw code.
export const TAG_LABELS: Readonly<Record<string, string>> = {
  DISABLE_DROP_OF_THOUGHTS: 'Loi de monde Drop of Thoughts désactivable',
  DISABLE_HANDSOME_MIGRANTS: 'Loi de monde Handsome Migrants désactivable',
  FAVORITE_ABOARD: 'Le favori est à bord',
  FAVORITE_PLOTTING: 'Le favori mène un complot',
  NAVIGATION: 'La navigation est découverte',
  NEW_AGE: 'Le monde bascule dans un nouvel âge',
  NEW_FAVORITE: 'Un nouveau favori est désigné',
};

// French labels for `world.metadata.age_id`, stripped of its `age_` prefix as the icon lookup is — WB's own English stays in `datas/world-ages.json`.
export const AGE_LABELS: Readonly<Record<string, string>> = {
  ash: 'Ère des Cendres',
  chaos: 'Ère du Chaos',
  dark: 'Ère des Ténèbres',
  despair: 'Ère du Désespoir',
  hope: "Ère de l'Espoir",
  ice: 'Ère de Glace',
  moon: 'Ère de la Lune',
  sun: 'Ère du Soleil',
  tears: 'Ère des Larmes',
  unknown: 'Ère inconnue',
  wonders: 'Ère des Merveilles',
};

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
  summon_hellstorm: 'Tempête infernale',
  summon_living_plants: 'Invocation de plantes vivantes',
  summon_meteor_rain: 'Invocation de météores',
  summon_skeletons: 'Invocation de squelettes',
  summon_stormfront: "Invocation d'une tempête",
  summon_thunderstorm: "Invocation d'un orage",
};

// French labels for kingdom diplomatic relation statuses (ally / enemy / neutral) — mirrors WB's runtime relation state derived from alliances + ongoing wars.
export const RELATION_STATUS_LABELS = { ally: 'Allié', enemy: 'Ennemi', neutral: 'Neutre' } as const;

// ng-zorro nz-tag colors per relation status — green for allies, red for active enemies, default for everything else.
export const RELATION_STATUS_NZ_COLORS = { ally: 'green', enemy: 'red', neutral: 'default' } as const;

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

// WB's 104 named species, French label per key — Python emits the `asset_id` as it does for biomes; the 126 unnamed assets fall through to their key.
export const SPECIES_NAMES: Readonly<Record<string, string>> = {
  acid_blob: 'Blob d\'acide',
  alien: 'Extraterrestre',
  alpaca: 'Alpaga',
  angle: 'Angle',
  armadillo: 'Tatou',
  assimilator: 'Assimilateur',
  bandit: 'Bandit',
  bear: 'Ours',
  bee: 'Abeille',
  beetle: 'Scarabée',
  bioblob: 'Bioblob',
  buffalo: 'Buffle',
  butterfly: 'Papillon',
  capybara: 'Capybara',
  cat: 'Chat',
  chicken: 'Poulet',
  civ_acid_gentleman: 'Gentleman acide',
  civ_alpaca: 'Charmaca',
  civ_armadillo: 'Armaldar',
  civ_bear: 'Grranth',
  civ_beetle: 'Dunglord',
  civ_buffalo: 'Buffolon',
  civ_candy_man: 'Homme Bonbon',
  civ_capybara: 'Chillbara',
  civ_cat: 'Meowmorph',
  civ_chicken: 'Pecklord',
  civ_cow: 'Mootaur',
  civ_crab: 'Crablin',
  civ_crocodile: 'Reptiloïde',
  civ_dog: 'Barkfolk',
  civ_fox: 'Slypaw',
  civ_frog: 'Ribbit',
  civ_garlic_man: 'Homme d\'ail',
  civ_goat: 'Herdor',
  civ_hyena: 'Lulclaw',
  civ_lemon_man: 'Homme Citron',
  civ_liliar: 'Lulliar',
  civ_monkey: 'Monke',
  civ_penguin: 'Coolbeak',
  civ_piranha: 'Gnapkin',
  civ_rabbit: 'Hopper',
  civ_rat: 'Nibling',
  civ_rhino: 'Armoroc',
  civ_scorpion: 'Scorp',
  civ_seal: 'Navy Seal',
  civ_sheep: 'Baakin',
  civ_snake: 'Snok',
  civ_turtle: 'Turtok',
  civ_unicorn: 'Punkcorn',
  civ_wolf: 'Howleer',
  cold_one: 'Les Froids',
  cow: 'Vache',
  crab: 'Crabe',
  crabzilla: 'Crabzilla',
  crocodile: 'Crocodile',
  crystal_sword: 'Épée en cristal',
  demon: 'Démon',
  dog: 'Chien',
  dragon: 'Dragon',
  druid: 'Druidesse',
  dwarf: 'Nain',
  elf: 'Elfe',
  evil_mage: 'Mage diabolique',
  fairy: 'Fée',
  fire_elemental: 'Élémentaire de Feu',
  fire_skull: 'Crâne enflammé',
  flower_bud: 'Bourgeon de Fleur',
  fly: 'Mouche',
  fox: 'Renard',
  frog: 'Grenouille',
  garl: 'Garl',
  ghost: 'Fantôme',
  goat: 'Chèvre',
  god_finger: 'Doigt Divin',
  grasshopper: 'Sauterelle',
  greg: 'Greg',
  human: 'Humain',
  hyena: 'Hyène',
  lil_pumpkin: 'Petite citrouille',
  living_house: 'Maison vivante',
  monkey: 'Singe',
  necromancer: 'Nécromancien',
  orc: 'Orc',
  ostrich: 'Autruche',
  penguin: 'Manchot',
  piranha: 'Piranhas',
  plague_doctor: 'Docteur de la peste',
  printer: 'Imprimante',
  rabbit: 'Lapin',
  raccoon: 'Raton laveur',
  rat: 'Rat',
  rhino: 'Rhinocéros',
  sand_spider: 'Araignée de sable',
  scorpion: 'Scorpion',
  seal: 'Phoque',
  sheep: 'Moutons',
  skeleton: 'Squelette',
  smore: 'Smore',
  snake: 'Serpent',
  snowman: 'Bonhomme de neige',
  turtle: 'Tortue',
  unicorn: 'Licorne',
  white_mage: 'Mage blanc',
  worm: 'Ver',
};

// French labels for `metadata.tenure_years` — names the post the years are counted for. Only these professions hold one.
export const TENURE_LABELS: Readonly<Record<string, string>> = { army_captain: 'Commandement', king: 'Règne', leader: 'Direction' };

// French labels for `war.war_type` — sourced from WB's `meta_wars` locale (war_type_*).
export const WAR_TYPE_LABELS = { conquest: 'Conquête', inspire: 'Inspirée', rebellion: 'Rébellion', spite: 'Dépit', whisper: 'Murmure' } as const;

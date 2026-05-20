import { Page } from './page.interface';
import { RarityCounts } from './rarity-counts.interface';

export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

export interface ChapterMeta {
  age_label: string;
  favorite: {
    age: number;
    asset_id: string;
    descriptor: string;
    equipment: RarityCounts;
    name: string;
    overview: {
      armor: number;
      armor_rank: number;
      attack_speed: number;
      attack_speed_rank: number;
      birth_rate: number;
      birth_rate_rank: number;
      births: number;
      children: number;
      critical_chance: number;
      critical_chance_rank: number;
      damage: number;
      damage_range: number;
      damage_range_rank: number;
      damage_rank: number;
      diplomacy: number;
      diplomacy_rank: number;
      earnings: number;
      earnings_rank: number;
      health_max: number;
      health_max_rank: number;
      intelligence: number;
      intelligence_rank: number;
      kills: number;
      kills_rank: number;
      level: number;
      level_rank: number;
      lifespan: number;
      lifespan_rank: number;
      mana_max: number;
      mana_max_rank: number;
      max_children: number;
      money: number;
      money_rank: number;
      renown: number;
      renown_rank: number;
      speed: number;
      speed_rank: number;
      stamina_max: number;
      stamina_max_rank: number;
      stewardship: number;
      stewardship_rank: number;
      warfare: number;
      warfare_rank: number;
    };
    sex: 'female' | 'male';
    stats: { happiness: number; health: number; mana: number; nutrition: number; stamina: number };
    traits: RarityCounts;
  } | null;
  tags: string[];
  title: string;
  world: {
    cumulative: {
      books_read: number;
      deaths: {
        eaten: number;
        explosion: number;
        fire: number;
        hunger: number;
        old_age: number;
        water: number;
        weapon: number;
      };
      plots_succeeded: number;
    };
    metadata: {
      age_id: string;
      world_time: number;
    };
    snapshot: {
      alliances: number;
      armies: number;
      books: number;
      cities: number;
      clans: number;
      cultures: number;
      diplomatic_relations: number;
      equipment: number;
      families: number;
      frozen_tiles: number;
      houses: number;
      kingdoms: number;
      languages: number;
      population: number;
      religions: number;
      subspecies: number;
      vegetation: number;
      wars: number;
      wild_creatures: number;
    };
  };
}

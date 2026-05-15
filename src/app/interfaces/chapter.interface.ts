import { Page } from './page.interface';
import { RarityCounts } from './rarity-counts.interface';

export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

export interface ChapterMeta {
  age: { id: string; label: string };
  favorite: {
    age: number;
    asset_id: string;
    descriptor: string;
    equipment: RarityCounts;
    name: string;
    overview: {
      damage_max: number;
      damage_min: number;
      health_max: number;
      health_max_rank: number;
      mana_max: number;
      mana_max_rank: number;
      stamina_max: number;
      stamina_max_rank: number;
    };
    sex: 'female' | 'male';
    stats: { happiness: number; health: number; mana: number; nutrition: number; stamina: number };
    traits: RarityCounts;
  } | null;
  tags: string[];
  title: string;
  world: {
    alliances: number;
    books: number;
    cities: number;
    clans: number;
    creatures: number;
    cultures: number;
    deaths: number;
    deaths_by_cause: {
      age: number;
      drowning: number;
      eaten: number;
      explosion: number;
      fire: number;
      hunger: number;
      water: number;
      weapon: number;
    };
    equipment: number;
    families: number;
    houses: number;
    kingdoms: number;
    languages: number;
    plants: number;
    population: number;
    religions: number;
    subspecies: number;
    wars: number;
  };
  world_time: number;
}

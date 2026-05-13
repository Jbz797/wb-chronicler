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
    overview: { damage_max: number; damage_min: number; health_max: number; health_max_rank: number };
    sex: 'female' | 'male';
    stats: { happiness: number; health: number; mana: number; nutrition: number };
    traits: RarityCounts;
  } | null;
  tags: string[];
  title: string;
  world_time: number;
}

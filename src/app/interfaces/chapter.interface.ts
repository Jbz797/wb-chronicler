import { Page } from './page.interface';

export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

export interface ChapterMeta {
  age: { id: string; label: string };
  favorite: {
    age: number;
    asset_id: string;
    descriptor: string;
    name: string;
    traits: { epic: number; legendary: number; normal: number; rare: number };
  } | null;
  tags: string[];
  title: string;
  world_time: number;
}

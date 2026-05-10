import { Page } from './page.interface';

export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

export interface ChapterMeta {
  age: string;
  favorite: { asset_id: string; descriptor: string; name: string } | null;
  tags: string[];
  title: string;
  world_time: number;
}

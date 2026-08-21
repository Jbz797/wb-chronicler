import { Boat } from './entities/boat.interface';
import { City } from './entities/city.interface';
import { Clan } from './entities/clan.interface';
import { Culture } from './entities/culture.interface';
import { Family } from './entities/family.interface';
import { Favorite } from './entities/favorite.interface';
import { Kingdom } from './entities/kingdom.interface';
import { Language } from './entities/language.interface';
import { Religion } from './entities/religion.interface';
import { Subspecies } from './entities/subspecies.interface';
import { World } from './entities/world.interface';
import { ChapterTier } from './types';

// One chronicle chapter: a nav Page plus its parsed chapter.json `meta` and preview image.
export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

// A parsed chapter.json: a block per overview panel — the world, the favorite and each body it belongs to — plus the age label and prose tags.
export interface ChapterMeta extends Record<ChapterTier, unknown> {
  age_label: string;
  boat: Boat | null;
  city: City | null;
  clan: Clan | null;
  culture: Culture | null;
  family: Family | null;
  favorite: Favorite | null;
  kingdom: Kingdom | null;
  language: Language | null;
  religion: Religion | null;
  subspecies: Subspecies | null;
  tags: string[];
  world: World;
}

// A reader destination: the static Précepte pages and, through `Chapter`, every chronicle.
export interface Page { label: string; mdUrl: string; slug: string }

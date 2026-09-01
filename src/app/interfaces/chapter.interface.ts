import { Alliance } from './entities/alliance.interface';
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
import { War } from './entities/war.interface';
import { World } from './entities/world.interface';
import { ChapterTier } from './types';

// One chronicle chapter as the nav knows it, off `saves/index.json`: what a row prints, without opening the chapter itself.
export interface Chapter extends Page { previewUrl: string; tags: string[] }

// One row of `saves/index.json`, written by `new.py`: enough to name and date a chapter, never enough to draw a panel.
export interface ChapterIndexEntry { n: number; tags: string[]; world_time: number }

// A parsed chapter.json: a block per overview panel — the world, the favorite and each body it belongs to — plus the age label and prose tags.
export interface ChapterMeta extends Record<ChapterTier, unknown> {
  alliance: Alliance | null;
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
  wars: War[]; // the crown's own, each answering for itself — its `kingdom.wars` names them, this block fields them
  world: World;
}

// A chapter whose `chapter.json` has been read — the one being read and the one before it, which the panels compare it to.
export interface LoadedChapter extends Chapter { meta: ChapterMeta }

// A reader destination: the static Précepte pages and, through `Chapter`, every chronicle.
export interface Page { label: string; mdUrl: string; slug: string }

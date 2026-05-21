import { Page } from './page.interface';
import { RarityCounts } from './rarity-counts.interface';

export interface Chapter extends Page { meta: ChapterMeta; previewUrl: string }

export interface ChapterMeta {
  age_label: string;
  favorite: {
    descriptor: string;
    equipment: RarityCounts;
    inventory: Record<string, number>;
    lover: {
      age: number;
      health_max: number;
      level: number;
      money: number;
      name: string;
      renown: number;
      sex: 'female' | 'male';
    } | null;
    metadata: {
      age: number;
      asset_id: string;
      name: string;
      sex: 'female' | 'male';
    };
    ranks: {
      armor: number;
      attack_speed: number;
      birth_rate: number;
      critical_chance: number;
      damage: number;
      damage_range: number;
      diplomacy: number;
      health_max: number;
      intelligence: number;
      kills: number;
      level: number;
      lifespan: number;
      loot: number;
      mana_max: number;
      money: number;
      renown: number;
      speed: number;
      stamina_max: number;
      stewardship: number;
      warfare: number;
    };
    stats: {
      armor: number;
      attack_speed: number;
      birth_rate: number;
      births: number;
      children: number;
      critical_chance: number;
      damage: number;
      damage_range: number;
      diplomacy: number;
      happiness: number;
      health: number;
      health_max: number;
      intelligence: number;
      kills: number;
      level: number;
      lifespan: number;
      loot: number;
      mana: number;
      mana_max: number;
      max_children: number;
      money: number;
      nutrition: number;
      renown: number;
      speed: number;
      stamina: number;
      stamina_max: number;
      stewardship: number;
      warfare: number;
    };
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
      equipment: number;
      families: number;
      frozen_tiles: number;
      houses: number;
      kingdoms: number;
      languages: number;
      population: number;
      relations: number;
      religions: number;
      subspecies: number;
      vegetation: number;
      wars: number;
      wild_creatures: number;
    };
  };
}

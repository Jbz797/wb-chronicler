import { CityRegistry, KingdomRegistry, PersonRegistry } from '../interfaces';

export const CHAPTER_REGISTRY = { slug: '' }; // Current chapter slug bridge for the marked renderers (crown asset paths are per-chapter).
export const CITY_REGISTRY: CityRegistry = {};
export const CITY_SIZE_TERMS = ['Foyer', 'Hameau', 'Village', 'Bourg', 'Cité', 'Grande cité', 'Métropole']; // Term per size tier (1-7) — the chronicler.md scale.
export const KINGDOM_REGISTRY: KingdomRegistry = {};
export const PERSON_REGISTRY: PersonRegistry = {};

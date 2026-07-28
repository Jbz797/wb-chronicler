import { CityRegistry, KingdomRegistry, PersonRegistry } from '../interfaces';

export const CITY_REGISTRY: CityRegistry = {};
export const CITY_SIZE_TERMS = ['Foyer', 'Hameau', 'Village', 'Bourg', 'Cité', 'Grande cité', 'Métropole']; // Term per size tier (1-7) — the chronicler.md scale.
export const KINGDOM_REGISTRY: KingdomRegistry = {};
export const PERSON_REGISTRY: PersonRegistry = {};
export const REALM_FALLBACK_HUE = '#B0B0B0'; // WB `Toolbox.color_grey` — worn by whoever answers to no crown: wild beasts, bandits, the exiled.

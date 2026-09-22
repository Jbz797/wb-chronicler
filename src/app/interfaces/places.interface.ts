import { MapPinKind } from './types';

// A named entry of the gazetteer on the fullscreen map, sited in percent of the picture so it holds at any size — `fontSize` in `cqw`, a spot's left to the sheet.
export interface MapPin { fontSize?: number; key: string; kind: MapPinKind; left: number; name: string; size?: number; spotKind?: string; top: number }

// A land or a closed water, by its centre of mass and its extent in tiles — `name` and `chapter` empty while the chronicle has not baptised it.
export interface PlaceArea { centroid: TilePoint; chapter: string; name: string; size: number }

// `history/places.json`, the chronicler's gazetteer: one file for the whole world, lands and waters keyed by their id, spots by their own name.
export interface Places { islands: Record<string, PlaceArea>; lakes: Record<string, PlaceArea>; places: Record<string, PlaceSpot> }

// A spot the chronicler named — its key is the name — sited by one tile and filed by what it is, in the chronicle's own word (`lisière`, `îlot`…).
export interface PlaceSpot { centroid: TilePoint; chapter: string; island_id?: number; kind: string }

// The map's extent in tiles — the preview's own size, WB drawing one pixel a tile.
export interface TileExtent { height: number; width: number }

// A tile in save coordinates: `y` grows north, where the picture's rows grow south.
export interface TilePoint { x: number; y: number }

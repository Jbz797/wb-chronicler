import { MapPinKind } from './types';

// A name's box on the fullscreen map, centred on its point, all in `cqw` — `fixed` for a land's, which the others step around.
export interface LabelBox { fixed: boolean; h: number; key: string; w: number; x: number; y: number }

// A named entry of the gazetteer on the fullscreen map, sited in percent of the picture so it holds at any size — `area` in km², `fontSize` in `cqw`.
export interface MapPin {
  area?: number;
  emoji?: string;
  fontSize?: number;
  key: string;
  kind: MapPinKind;
  left: number;
  name: string;
  spotKind?: string;
  top: number;
}

// A land or a closed water, by its centre of mass and its extent in tiles — `name` and `chapter` empty while the chronicle has not baptised it.
export interface PlaceArea { centroid: TilePoint; chapter: string; name: string; size: number }

// `history/places.json`, the chronicler's gazetteer: one file for the whole world, lands and waters keyed by their id, spots by their own name.
export interface Places {
  islands: Record<string, PlaceArea>;
  lakes: Record<string, PlaceArea>;
  places: Record<string, PlaceSpot>;
  rivers?: Record<string, PlaceArea>; // absent, as `seas`, from a gazetteer seeded before they were, until its next chapter
  seas?: Record<string, PlaceArea>;
}

// The map's extent in tiles — the preview's own size, WB drawing one pixel a tile.
export interface TileExtent { height: number; width: number }

// A tile in save coordinates: `y` grows north, where the picture's rows grow south.
export interface TilePoint { x: number; y: number }

// A spot the chronicler named (its key), sited by one tile, filed in his own word (`lisière`, `îlot`…), marked by his `emoji` — `island_id` is `new.py`'s alone.
interface PlaceSpot { centroid: TilePoint; chapter: string; emoji: string; kind: string }

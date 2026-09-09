import { RankedStatKind } from './types';

export interface RankedStatSnapshot { rank?: number; value: number }

// `icon` names the sprite in `assets/img/stats/`, which is filed by concept: the roster key may carry a `_max` the drawing never had.
export interface StatConfig { deltaSuffix?: string; icon?: string; key: RankedStatKind; label: string; numberFormat?: string; showRank?: boolean; suffix?: string }

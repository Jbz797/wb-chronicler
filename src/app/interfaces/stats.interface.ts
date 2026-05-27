import { RankedStatKind } from './types';

export interface RankedStatSnapshot { rank_in_species?: number; value: number }
export interface RarityCounts { epic: number; legendary: number; normal: number; rare: number }
export interface StatConfig { deltaSuffix?: string; key: RankedStatKind; label: string; numberFormat?: string; showRank?: boolean; suffix?: string }

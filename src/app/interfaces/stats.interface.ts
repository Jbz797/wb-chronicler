import { RankedStatKind } from './types';

export interface RankedStatSnapshot { rank?: number; value: number }
export interface StatConfig { deltaSuffix?: string; key: RankedStatKind; label: string; numberFormat?: string; showRank?: boolean; suffix?: string }

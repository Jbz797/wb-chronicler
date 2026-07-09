import { Pipe, PipeTransform } from '@angular/core';

// `.tier-*` styles live in `src/styles.scss`.
@Pipe({ name: 'tier', standalone: true })
export class TierPipe implements PipeTransform {

  // Anchored on WB happiness: `tier-high` = `isHappy` (≥ 0.6), `tier-low` = `isUnhappy` (< 0.3); mid = neutral band, full = excellence.
  public transform(current: number, max: number): string {
    const r = max > 0 ? current / max : 0;
    if (r >= 0.8) return 'tier-full';
    if (r >= 0.6) return 'tier-high';
    if (r >= 0.3) return 'tier-mid';
    return 'tier-low';
  }

}

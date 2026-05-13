import { Pipe, PipeTransform } from '@angular/core';

// `.tier-*` styles live in `src/styles.scss`.
@Pipe({ name: 'tier', standalone: true })
export class TierPipe implements PipeTransform {

  public transform(current: number, max: number): string {
    const r = max > 0 ? current / max : 0;
    if (r >= 0.75) return 'tier-full';
    if (r >= 0.5) return 'tier-high';
    if (r >= 0.25) return 'tier-mid';
    return 'tier-low';
  }

}

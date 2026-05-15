import { Pipe, PipeTransform } from '@angular/core';

// |v| < 100 → raw integer ; |v| ≥ 100 → `X.X K`.
@Pipe({ name: 'compact', standalone: true })
export class CompactPipe implements PipeTransform {

  public transform(value: number): string {
    if (Math.abs(value) < 100) return String(value);
    return `${(value / 1000).toFixed(1)} K`;
  }

}

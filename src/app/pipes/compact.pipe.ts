import { Pipe, PipeTransform } from '@angular/core';

// |v| < 100 → raw integer ; |v| ≥ 100 → `X K` or `X.X K` (no trailing `.0`).
@Pipe({ name: 'compact', standalone: true })
export class CompactPipe implements PipeTransform {

  public transform(value: number): string {
    if (Math.abs(value) < 100) return String(value);
    return `${Number.parseFloat((value / 1000).toFixed(1))} K`;
  }

}

import { Pipe, PipeTransform } from '@angular/core';

// |v| < 100 → raw int or `X.X` (1-decimal, no trailing `.0`) ; |v| ≥ 100 → `X K` or `X.X K`.
@Pipe({ name: 'compact', standalone: true })
export class CompactPipe implements PipeTransform {

  public transform(value: number): string {
    if (Math.abs(value) < 100) return String(Math.round(value * 10) / 10);
    return `${Number.parseFloat((value / 1000).toFixed(1))} K`;
  }

}

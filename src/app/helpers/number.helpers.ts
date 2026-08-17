// How a stat row shortens a number. Both pipes read it, so the threshold and the wording live in one place rather than drifting apart.
export class NumberHelpers {

  // |v| < 100 → raw int or 1-decimal `X.X`; |v| ≥ 100 → `X K` or `X.X K`. A decimal still means something below the threshold; above it `K` reads faster.
  public static compact(value: number): string {
    if (!this.isCompacted(value)) return String(Math.round(value * 10) / 10);
    return `${Number((value / 1000).toFixed(1))} K`;
  }

  // Whether the `K` form hides digits — the only case worth a tooltip, `ExactPipe` reading it so the threshold is stated once.
  public static isCompacted = (value: number): boolean => Math.abs(value) >= 100;

}

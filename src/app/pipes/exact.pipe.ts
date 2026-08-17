import { formatNumber } from '@angular/common';
import { inject, LOCALE_ID, Pipe, PipeTransform } from '@angular/core';

import { NumberHelpers } from '../helpers';

// The whole number behind a `X K`, for a `title` — `null` below the threshold, where the row prints it whole, and Angular then drops the attribute entirely.
@Pipe({ name: 'exact', standalone: true })
export class ExactPipe implements PipeTransform {

  private readonly _locale = inject(LOCALE_ID);

  public transform = (value: number): string | null => NumberHelpers.isCompacted(value) ? formatNumber(value, this._locale, '1.0-0') : null;

}

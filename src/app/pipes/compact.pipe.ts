import { Pipe, PipeTransform } from '@angular/core';

import { NumberHelpers } from '../helpers';

// The shortened form a stat row prints — see `NumberHelpers.compact`; `ExactPipe` hands back what it dropped.
@Pipe({ name: 'compact', standalone: true })
export class CompactPipe implements PipeTransform {

  public transform = (value: number): string => NumberHelpers.compact(value);

}

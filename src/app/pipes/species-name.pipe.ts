import { Pipe, PipeTransform } from '@angular/core';

import { SPECIES_NAMES } from '../constants';

// WB's `asset_id` to its French label. Python emits the key alone — a species is fixed vocabulary, so the wording is the UI's, as a biome's is.
@Pipe({ name: 'speciesName', standalone: true })
export class SpeciesNamePipe implements PipeTransform {

  // The 126 assets WB ships unnamed fall through to their key, which reads as the English id rather than as a blank.
  public transform(assetId: string | undefined): string {
    return assetId ? SPECIES_NAMES[assetId] ?? assetId : '';
  }

}

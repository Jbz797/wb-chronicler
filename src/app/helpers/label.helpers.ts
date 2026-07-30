import { GenderedLabel } from '../interfaces';

// French labels that agree with a person — everything the panels print about someone whose sex the save records.
export class LabelHelpers {

  // WB stores `male`/`female`, and only a handful of actors read `female`; anything else falls to the masculine, which is also French's default form.
  public static gendered(label: GenderedLabel | undefined, sex: string | undefined): string {
    if (label === undefined) return '';
    return typeof label === 'string' ? label : label[sex === 'female' ? 'f' : 'm'];
  }

}

import { TranslateService } from '@ngx-translate/core';

// Labels that agree with a person — everything the panels print about someone whose sex the save records.
export class LabelHelpers {

  // WB stores `male`/`female`, anything else falling to the masculine — and a tongue that does not inflect carries the bare key the gendered one falls back to.
  public static gendered(translate: TranslateService, base: string, sex: string | undefined): string {
    const key = `${base}_${sex === 'female' ? 'f' : 'm'}`;
    const label = translate.instant(key) as string;
    return label === key ? (translate.instant(base) as string) : label;
  }

}

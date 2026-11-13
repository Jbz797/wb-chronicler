import { TranslateService } from '@ngx-translate/core';

import { KINGDOM_REGISTRY } from '../constants';
import { PersonInfo } from '../interfaces';

// Labels that agree with a person — everything the panels print about someone whose sex the save records.
export class LabelHelpers {

  // WB stores `male`/`female`, anything else falling to the masculine — and a tongue that does not inflect carries the bare key the gendered one falls back to.
  public static gendered(translate: TranslateService, base: string, sex: string | undefined): string {
    const key = `${base}_${sex === 'female' ? 'f' : 'm'}`;
    const label = translate.instant(key) as string;
    return label === key ? (translate.instant(base) as string) : label;
  }

  // A person's plate on hover, panels and prose alike: blood tie to the favourite, species, crown at this chapter, age or the year they fell.
  public static personAbout(translate: TranslateService, person: PersonInfo): string {
    const age = person.age === undefined ? undefined : `${person.age}${translate.instant('ui_years') as string}`;
    const died = person.died === undefined ? undefined : `${this.gendered(translate, 'ui_died', person.sex)} ${person.died}`;
    const kin = person.kin ? this.gendered(translate, `kin_${person.kin}`, person.sex) : undefined;
    const realm = person.kingdom === undefined ? undefined : KINGDOM_REGISTRY[String(person.kingdom)]?.name;
    return [kin, translate.instant(`species_${person.asset_id}`) as string, realm, age, died].filter(Boolean).join(' · ');
  }

}

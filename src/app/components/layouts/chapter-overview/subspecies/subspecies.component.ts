import { Component, computed, inject } from '@angular/core';

import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { BreakdownComponent, RankedStatComponent, TraitSummaryComponent } from '..';
import { RankedStatKind } from '../../../../interfaces';
import { ChroniclerService } from '../../../../services';
import { LeadersComponent } from '../leaders/leaders.component';

@Component({
  selector: 'app-subspecies',
  imports: [BreakdownComponent, LeadersComponent, NzDescriptionsModule, RankedStatComponent, TraitSummaryComponent, TranslatePipe],
  templateUrl: './subspecies.component.html',
})
export class SubspeciesComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _translate = inject(TranslateService);

  protected readonly subspecies = computed(() => this._chronicler.currentChapter()?.meta.subspecies ?? null);
  // The biome in the reader's tongue, WB's key standing in for one its locales never named — `null` where it set no variant, which drops the row.
  protected readonly biomeName = computed(() => {
    const key = this.subspecies()?.metadata.biome;
    if (!key) return null;
    const label = this._translate.instant(`biome_${key}`) as string;
    return label === `biome_${key}` ? key : label;
  });
  // WB writes these only once the biology has scored on them, so a row appears the year it first matters — same rule as the clan's and the lineage's.
  protected readonly lifetimeStats = computed<{ icon: string; inverted: boolean; label: string; stat: RankedStatKind }[]>(() => {
    const m = this.subspecies()?.metadata;
    if (!m) return [];
    const rows = [
      { icon: 'assets/img/world/births.png', inverted: false, label: 'ui_births', shown: !!m.births, stat: 'births' as const },
      { icon: 'assets/img/world/deaths.png', inverted: true, label: 'ui_deaths', shown: !!m.deaths, stat: 'deaths' as const },
      { icon: 'assets/img/professions/warrior.png', inverted: false, label: 'ui_warriors', shown: true, stat: 'warriors' as const },
      { icon: 'assets/img/stats/kills.png', inverted: false, label: 'ui_kills', shown: !!m.kills, stat: 'kills' as const },
    ];
    return rows.filter(r => r.shown).map(({ icon, inverted, label, stat }) => ({ icon, inverted, label, stat }));
  });

}

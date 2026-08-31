import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { NgScrollbarModule } from 'ngx-scrollbar';

import { AGE_LABELS, CITY_SIZE_TERMS, HISTORY_DIR, KINGDOM_SIZE_TERMS } from '../../../constants';
import { ChapterOverviewPanel, ChapterTier, WorldInfo } from '../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../services';

import { AllianceComponent } from './alliance/alliance.component';
import { CityComponent } from './city/city.component';
import { ClanComponent } from './clan/clan.component';
import { CultureComponent } from './culture/culture.component';
import { FamilyComponent } from './family/family.component';
import { FavoriteComponent } from './favorite/favorite.component';
import { KingdomComponent } from './kingdom/kingdom.component';
import { LanguageComponent } from './language/language.component';
import { PanelExtraComponent } from './panel-extra/panel-extra.component';
import { ReligionComponent } from './religion/religion.component';
import { SubspeciesComponent } from './subspecies/subspecies.component';
import { WarsComponent } from './wars/wars.component';
import { WorldStatsComponent } from './world-stats/world-stats.component';

import { NewBadgeComponent } from '.';

@Component({
  selector: 'app-chapter-overview',
  imports: [
    AllianceComponent,
    CityComponent,
    ClanComponent,
    CultureComponent,
    FamilyComponent,
    FavoriteComponent,
    KingdomComponent,
    LanguageComponent,
    NewBadgeComponent,
    NgScrollbarModule,
    NzCollapseModule,
    NzDividerModule,
    NzEmptyModule,
    NzTagModule,
    PanelExtraComponent,
    ReligionComponent,
    SubspeciesComponent,
    WarsComponent,
    WorldStatsComponent,
  ],
  templateUrl: './chapter-overview.component.html',
  styleUrl: './chapter-overview.component.scss',
})
export class ChapterOverviewComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _http = inject(HttpClient);
  private readonly _registry = inject(RegistryService);

  protected readonly ageLabels = AGE_LABELS;

  protected currentChapter = this._chronicler.currentChapter;

  protected readonly activePanel = signal<ChapterOverviewPanel>(this._restoreActivePanel());
  // Panel title honours the `chronicler.md` population scale — never call a three-soul hamlet a « cité ».
  protected readonly cityTerm = computed(() => {
    const id = this.currentChapter()?.meta.city?.metadata.id;
    const size = id === undefined ? undefined : this._registry.cities()[String(id)]?.size;
    return (size ? CITY_SIZE_TERMS[size - 1] : undefined) ?? 'Village';
  });
  // The world turned an age since the previous chapter — the menu badges the chapter itself, this names the age it turned to.
  protected readonly isNewAge = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.world.metadata.age_id;
    return !!previous && previous !== this.currentChapter()?.meta.world.metadata.age_id;
  });
  // Panel title on the same scale, off the crown's own city count — uneven rungs, so a lookup rather than a tier index.
  protected readonly kingdomTerm = computed(() => {
    const cities = this.currentChapter()?.meta.kingdom?.metadata.cities ?? 0;
    const rung = [0, 1, 2, 5, 9].findLastIndex(cap => cities > cap) + 1;
    return KINGDOM_SIZE_TERMS[rung] ?? 'Royaume';
  });
  protected readonly world = toSignal(this._http.get<WorldInfo>(`${HISTORY_DIR}/world.json`));

  // ng-zorro 22 dropped `nzDisabled` for `nzCollapsible`, whose union has no "default" member — `undefined` restores it (cast for `exactOptionalPropertyTypes`).
  protected collapsible = (enabled: unknown): 'disabled' | 'header' | 'icon' => (enabled ? undefined : 'disabled') as 'disabled';

  // The body a panel is about has changed hands since the previous chapter — the favorite moved to another clan, another creed, or is himself a successor.
  protected isNewPanel = (panel: ChapterTier): boolean => {
    const previous = this._chronicler.previousChapter()?.meta[panel]?.metadata;
    return !!previous && !!this.currentChapter()?.meta[panel]?.metadata && !this._chronicler.carriesOver(panel);
  };

  // Persist the active panel to sessionStorage so it survives reloads and page changes.
  protected onPanelToggle(panel: ChapterOverviewPanel, isActive: boolean): void {
    const next = isActive ? panel : 'world-stats';
    this.activePanel.set(next);
    sessionStorage.setItem('chapter-overview.active-panel', next);
  }

  // Type guard on the persisted panel name — a `Record`, not a list, so a panel added to the union but forgotten here breaks the build instead of failing silently.
  private _isPanel(v: string | null): v is ChapterOverviewPanel {
    const panels: Record<ChapterOverviewPanel, true> = {
      alliance: true,
      city: true,
      clan: true,
      culture: true,
      family: true,
      favorite: true,
      kingdom: true,
      language: true,
      religion: true,
      subspecies: true,
      wars: true,
      'world-stats': true,
    };
    return Object.keys(panels).includes(v ?? '');
  }

  // Read the stored panel and fall back to `world-stats` when nothing valid is found.
  private _restoreActivePanel(): ChapterOverviewPanel {
    const stored = sessionStorage.getItem('chapter-overview.active-panel');
    return this._isPanel(stored) ? stored : 'world-stats';
  }

}

import { HttpClient } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { NgScrollbarModule } from 'ngx-scrollbar';

import { CITY_SIZE_TERMS, HISTORY_DIR, KINGDOM_SIZE_TERMS } from '../../../constants';
import { FreshDirective } from '../../../directives';
import { WorldHelpers } from '../../../helpers';
import { ChapterOverviewPanel, ChapterTier, WorldInfo } from '../../../interfaces';
import { ChroniclerService, RegistryService } from '../../../services';

import { AllianceComponent } from './alliance/alliance.component';
import { BannerGarlandComponent } from './banner-garland/banner-garland.component';
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
    BannerGarlandComponent,
    CityComponent,
    ClanComponent,
    CultureComponent,
    FamilyComponent,
    FavoriteComponent,
    FreshDirective,
    KingdomComponent,
    LanguageComponent,
    NewBadgeComponent,
    NgScrollbarModule,
    NzCollapseModule,
    NzEmptyModule,
    NzTagModule,
    NzTooltipModule,
    PanelExtraComponent,
    ReligionComponent,
    SubspeciesComponent,
    TranslatePipe,
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
  private readonly _translate = inject(TranslateService);

  protected currentChapter = this._chronicler.currentChapter;

  protected readonly activePanel = signal<ChapterOverviewPanel | null>(this._restoreActivePanel()); // `null` once « Monde » itself is shut: every panel closed
  // Panel title honours the `chronicler.md` population scale — never call a three-soul hamlet a « cité ». The registry leaves `size` unsaid at 1, its floor.
  protected readonly cityTerm = computed(() => {
    const id = this.currentChapter()?.meta.city?.metadata.id;
    const entry = id === undefined ? undefined : this._registry.cities()[String(id)];
    return this._translate.instant((entry ? CITY_SIZE_TERMS[(entry.size ?? 1) - 1] : undefined) ?? 'ui_village') as string;
  });

  // What a panel shows this chapter: « Monde » has no block, a bare world leaving it nothing; a tier or the wars, their block — `chapter.json` keeps no empty one.
  private readonly _hasBody = (panel: ChapterOverviewPanel): boolean => {
    const meta = this.currentChapter()?.meta;
    return panel === 'world-stats' ? this.worldHasContent() : !!meta && Object.hasOwn(meta, panel);
  };
  // A panel stands open with a body in it — the header then shrinks to a band, the age's scene shown whole while the collapse sits shut.
  protected readonly hasOpenPanel = computed(() => {
    const panel = this.activePanel();
    return !!panel && this._hasBody(panel);
  });
  // Panel title off the crown's city count, rungs uneven so a lookup — and no crown takes the plain word, the lowest rung meaning a realm that lost its cities.
  protected readonly kingdomTerm = computed(() => {
    const kingdom = this.currentChapter()?.meta.kingdom;
    const rung = [0, 1, 2, 5, 9].findLastIndex(cap => (kingdom?.metadata.cities ?? 0) > cap) + 1;
    return this._translate.instant((kingdom ? KINGDOM_SIZE_TERMS[rung] : undefined) ?? 'ui_kingdom') as string;
  });
  protected readonly world = toSignal(this._http.get<WorldInfo>(`${HISTORY_DIR}/world.json`));
  // A bare world with nothing to count, no death, no scheme and no record leaves « Monde » without a line: its panel is disabled, as an empty tier's is.
  protected readonly worldHasContent = computed(() => {
    const world = this.currentChapter()?.meta.world;
    return !!world && WorldHelpers.hasContent(world, this._chronicler.previousChapter()?.meta.world);
  });

  // ng-zorro 22 dropped `nzDisabled` for `nzCollapsible`, whose union has no "default" member — `undefined` restores it (cast for `exactOptionalPropertyTypes`).
  protected collapsible = (panel: ChapterOverviewPanel): 'disabled' | 'header' | 'icon' => (this._hasBody(panel) ? undefined : 'disabled') as 'disabled';

  // The panel's body is new to the favorite since the previous chapter — joined, founded, or changed hands. C1 has no chapter before to be new against.
  protected isNewPanel(panel: ChapterTier): boolean {
    return !!this._chronicler.previousChapter() && !!this.currentChapter()?.meta[panel]?.metadata && !this._chronicler.carriesOver(panel);
  }

  // A body this chapter does not carry leaves its panel `disabled`, so a name restored from the session would open it on an empty strip nothing could shut.
  protected isOpen = (panel: ChapterOverviewPanel): boolean => this.activePanel() === panel && this._hasBody(panel);

  // Persist the active panel to sessionStorage so it survives reloads and page changes. A panel shut falls back to « Monde », which shut leaves none open.
  protected onPanelToggle(panel: ChapterOverviewPanel, isActive: boolean): void {
    const next = isActive ? panel : (panel === 'world-stats' ? null : 'world-stats');
    this.activePanel.set(next);
    sessionStorage.setItem('chapter-overview.active-panel', next ?? '');
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

  // Read the stored panel — an empty one meaning all shut — and fall back to `world-stats` when nothing valid is found.
  private _restoreActivePanel(): ChapterOverviewPanel | null {
    const stored = sessionStorage.getItem('chapter-overview.active-panel');
    if (stored === '') return null;
    return this._isPanel(stored) ? stored : 'world-stats';
  }

}

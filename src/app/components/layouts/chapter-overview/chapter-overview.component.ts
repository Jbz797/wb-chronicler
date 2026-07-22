import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { HISTORY_DIR } from '../../../constants';
import { ChapterOverviewPanel, World } from '../../../interfaces';
import { ChroniclerService } from '../../../services';
import { CityTagComponent, KingdomTagComponent, PersonTagComponent } from '../../tags';

import { CityComponent } from './city/city.component';
import { FavoriteComponent } from './favorite/favorite.component';
import { KingdomComponent } from './kingdom/kingdom.component';
import { WorldStatsComponent } from './world-stats/world-stats.component';

@Component({
  selector: 'app-chapter-overview',
  imports: [
    CityComponent,
    CityTagComponent,
    FavoriteComponent,
    KingdomComponent,
    KingdomTagComponent,
    NzCollapseModule,
    NzDividerModule,
    NzEmptyModule,
    PersonTagComponent,
    WorldStatsComponent,
  ],
  templateUrl: './chapter-overview.component.html',
  styleUrl: './chapter-overview.component.scss',
})
export class ChapterOverviewComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _http = inject(HttpClient);

  protected currentChapter = this._chronicler.currentChapter;

  protected readonly activePanel = signal<ChapterOverviewPanel>(this._restoreActivePanel());
  protected readonly world = toSignal(this._http.get<World>(`${HISTORY_DIR}/world.json`));

  // ng-zorro 22 dropped `nzDisabled` for `nzCollapsible`, whose union has no "default" member — `undefined` restores it (cast for `exactOptionalPropertyTypes`).
  protected collapsible = (enabled: unknown): 'disabled' | 'header' | 'icon' => (enabled ? undefined : 'disabled') as 'disabled';

  // Persist the active panel to sessionStorage so it survives reloads and page changes.
  protected onPanelToggle(panel: ChapterOverviewPanel, isActive: boolean): void {
    const next = isActive ? panel : 'world-stats';
    this.activePanel.set(next);
    sessionStorage.setItem('chapter-overview.active-panel', next);
  }

  private _isPanel(v: string | null): v is ChapterOverviewPanel {
    const panels: string[] = ['city', 'favorite', 'kingdom', 'world-stats'];
    return panels.includes(v ?? '');
  }

  // Read the stored panel and fall back to `world-stats` when nothing valid is found.
  private _restoreActivePanel(): ChapterOverviewPanel {
    const stored = sessionStorage.getItem('chapter-overview.active-panel');
    return this._isPanel(stored) ? stored : 'world-stats';
  }

}

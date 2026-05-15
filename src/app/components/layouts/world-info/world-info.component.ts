import { HttpClient } from '@angular/common/http';
import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzEmptyModule } from 'ng-zorro-antd/empty';

import { HISTORY_DIR } from '../../../constants';
import { RarityCounts, World, WorldStat } from '../../../interfaces';
import { CompactPipe, TierPipe } from '../../../pipes';
import { ChroniclerService } from '../../../services/chronicler.service';
import { DeltaComponent, RankedStatComponent, RarityStatsComponent } from '../../misc';

@Component({
  selector: 'app-world-info',
  imports: [
    CompactPipe,
    DeltaComponent,
    NzCollapseModule,
    NzDescriptionsModule,
    NzDividerModule,
    NzEmptyModule,
    RankedStatComponent,
    RarityStatsComponent,
    TierPipe,
  ],
  templateUrl: './world-info.component.html',
  styleUrl: './world-info.component.scss',
})
export class WorldInfoComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Per-bucket deltas vs the previous favorite. `null` when no comparable previous favorite — ranked stats handle their own deltas.
  protected readonly deltas = computed(() => {
    const current = this.currentChapter()?.meta.favorite;
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    if (!current || !previous) return null;

    const diffCounts = (a: RarityCounts, b: RarityCounts): RarityCounts => ({
      epic: a.epic - b.epic,
      legendary: a.legendary - b.legendary,
      normal: a.normal - b.normal,
      rare: a.rare - b.rare,
    });

    return {
      damage: (current.overview.damage_min + current.overview.damage_max) - (previous.overview.damage_min + previous.overview.damage_max),
      equipment: diffCounts(current.equipment, previous.equipment),
      traits: diffCounts(current.traits, previous.traits),
    };
  });
  protected readonly world = toSignal(inject(HttpClient).get<World>(`${HISTORY_DIR}/world.json`));
  // Display order — left→right, top→bottom (mirrors the in-game stats panel).
  protected readonly worldStats: { key: WorldStat; label: string; useDelta?: boolean }[] = [
    { key: 'deaths', label: 'Morts récents', useDelta: true },
    { key: 'population', label: 'Population' },
    { key: 'creatures', label: 'Créatures' },
    { key: 'plants', label: 'Végétation' },
    { key: 'houses', label: 'Maisons' },
    { key: 'wars', label: 'Guerres' },
    { key: 'subspecies', label: 'Sous-espèces' },
    { key: 'kingdoms', label: 'Royaumes' },
    { key: 'cities', label: 'Villes' },
    { key: 'families', label: 'Familles' },
    { key: 'clans', label: 'Clans' },
    { key: 'alliances', label: 'Alliances' },
    { key: 'languages', label: 'Langues' },
    { key: 'cultures', label: 'Cultures' },
    { key: 'religions', label: 'Religions' },
    { key: 'books', label: 'Livres' },
    { key: 'equipment', label: 'Équipement' },
  ];
  // Per-stat delta on `meta.world` — `null` when no previous chapter to compare.
  protected readonly worldDeltas = computed(() => {
    const current = this.currentChapter()?.meta.world;
    const previous = this._chronicler.previousChapter()?.meta.world;
    if (!current || !previous) return null;
    return Object.fromEntries(this.worldStats.map(({ key }) => [key, current[key] - previous[key]])) as Record<WorldStat, number>;
  });

}

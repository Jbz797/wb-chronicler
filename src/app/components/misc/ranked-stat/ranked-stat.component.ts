import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { ChapterMeta, RankedStatKind, RankedStatSnapshot } from '../../../interfaces';
import { TierPipe } from '../../../pipes';
import { ChroniclerService } from '../../../services/chronicler.service';
import { DeltaComponent } from '../delta/delta.component';

@Component({
  selector: 'app-ranked-stat',
  imports: [DecimalPipe, DeltaComponent, TierPipe],
  templateUrl: './ranked-stat.component.html',
  styleUrl: './ranked-stat.component.scss',
})
export class RankedStatComponent {

  public readonly stat = input.required<RankedStatKind>();

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly data = computed(() => {
    const current = this._chronicler.currentChapter()?.meta.favorite;
    if (!current) return null;

    const previous = this._chronicler.previousChapter()?.meta.favorite ?? null;
    const c = this._resolve(current);
    const p = previous ? this._resolve(previous) : null;

    return {
      ...c,
      rankDelta: p ? c.rank - p.rank : undefined,
      valueDelta: p ? c.max - p.max : undefined,
    };
  });
  // 1-decimal precision for stats stored as floats (damage_range); integer otherwise.
  protected readonly numberFormat = computed(() => this.stat() === 'damage_range' ? '1.1-1' : '1.0-0');

  // Per-kind field accessor — keeps `overview[<computed key>]` off the hot path and stays type-safe.
  private _resolve(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    if (k === 'armor') return { max: f.overview.armor, rank: f.overview.armor_rank };
    if (k === 'damage') return { max: f.overview.damage, rank: f.overview.damage_rank };
    if (k === 'damage_range') return { max: f.overview.damage_range, rank: f.overview.damage_range_rank };
    if (k === 'health') return { current: f.stats.health, max: f.overview.health_max, rank: f.overview.health_max_rank };
    if (k === 'mana') return { current: f.stats.mana, max: f.overview.mana_max, rank: f.overview.mana_max_rank };
    return { current: f.stats.stamina, max: f.overview.stamina_max, rank: f.overview.stamina_max_rank };
  }

}

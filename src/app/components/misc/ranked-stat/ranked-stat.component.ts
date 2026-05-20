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
  // Suffix propagated to the delta tag — only kept for non-unit suffixes (`%`).
  protected readonly deltaSuffix = computed(() => this.stat() === 'critical_chance' ? '%' : '');
  // 1-decimal precision for stats stored as floats (damage_range); integer otherwise.
  protected readonly numberFormat = computed(() => this.stat() === 'damage_range' ? '1.1-1' : '1.0-0');
  // Stats where a high value is neither good nor bad (just stylistic) — the rank is hidden.
  protected readonly showRank = computed(() => this.stat() !== 'damage_range');
  // Trailing suffix for the headline value (percentages, units, etc).
  protected readonly suffix = computed(() => {
    const k = this.stat();
    if (k === 'critical_chance') return '%';
    if (k === 'lifespan') return ' ans';
    return '';
  });

  // Per-kind field accessor — pulls value/rank from the right section (cumulative for life-long
  // counters, snapshot for instant-T stats; `f.stats` carries the current health/mana/stamina).
  private _resolve(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    if (k === 'armor') return { max: f.snapshot.armor, rank: f.ranks.armor };
    if (k === 'attack_speed') return { max: f.snapshot.attack_speed, rank: f.ranks.attack_speed };
    if (k === 'birth_rate') return { max: f.snapshot.birth_rate, rank: f.ranks.birth_rate };
    if (k === 'critical_chance') return { max: f.snapshot.critical_chance, rank: f.ranks.critical_chance };
    if (k === 'damage') return { max: f.snapshot.damage, rank: f.ranks.damage };
    if (k === 'damage_range') return { max: f.snapshot.damage_range, rank: f.ranks.damage_range };
    if (k === 'diplomacy') return { max: f.snapshot.diplomacy, rank: f.ranks.diplomacy };
    if (k === 'health') return { current: f.stats.health, max: f.snapshot.health_max, rank: f.ranks.health_max };
    if (k === 'intelligence') return { max: f.snapshot.intelligence, rank: f.ranks.intelligence };
    if (k === 'kills') return { max: f.snapshot.kills, rank: f.ranks.kills };
    if (k === 'level') return { max: f.snapshot.level, rank: f.ranks.level };
    if (k === 'lifespan') return { max: f.snapshot.lifespan, rank: f.ranks.lifespan };
    if (k === 'loot') return { max: f.snapshot.loot, rank: f.ranks.loot };
    if (k === 'mana') return { current: f.stats.mana, max: f.snapshot.mana_max, rank: f.ranks.mana_max };
    if (k === 'money') return { max: f.snapshot.money, rank: f.ranks.money };
    if (k === 'renown') return { max: f.snapshot.renown, rank: f.ranks.renown };
    if (k === 'speed') return { max: f.snapshot.speed, rank: f.ranks.speed };
    if (k === 'stamina') return { current: f.stats.stamina, max: f.snapshot.stamina_max, rank: f.ranks.stamina_max };
    if (k === 'stewardship') return { max: f.snapshot.stewardship, rank: f.ranks.stewardship };
    return { max: f.snapshot.warfare, rank: f.ranks.warfare };
  }

}

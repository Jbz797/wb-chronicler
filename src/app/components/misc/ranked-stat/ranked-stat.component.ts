import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { KINGDOM_META_STATS } from '../../../constants';
import { ChapterMeta, KingdomMetaStat, RankedStatKind, RankedStatSnapshot } from '../../../interfaces';
import { TierPipe } from '../../../pipes';
import { ChroniclerService } from '../../../services';
import { DeltaComponent } from '../delta/delta.component';

@Component({
  selector: 'app-ranked-stat',
  imports: [DecimalPipe, DeltaComponent, TierPipe],
  templateUrl: './ranked-stat.component.html',
  styleUrl: './ranked-stat.component.scss',
})
export class RankedStatComponent {

  public readonly deltaSuffix = input<string>('');
  public readonly hideDelta = input<boolean>(false);
  public readonly numberFormat = input<string>('1.0-0');
  public readonly showRank = input<boolean>(true);
  public readonly source = input<'favorite' | 'kingdom'>('favorite');
  public readonly stat = input.required<RankedStatKind>();
  public readonly suffix = input<string>('');

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly data = computed(() => {
    const current = this._sourceOf(this._chronicler.currentChapter()?.meta);
    if (!current) return null;

    const previous = this._sourceOf(this._chronicler.previousChapter()?.meta);
    const c = this._resolve(current);
    const p = previous ? this._resolve(previous) : null;

    const valueDelta = this.hideDelta() ? undefined : (p ? c.value - p.value : undefined);
    return { ...c, rankStatus: this._rankStatus(c.rank, p?.rank, !!p), valueDelta };
  });
  // Live gauge value for stats that have a cap (health/mana/stamina). `null` for all others.
  protected readonly gaugeValue = computed(() => {
    const k = this.stat();
    const s = this._chronicler.currentChapter()?.meta.favorite?.stats;
    if (k === 'health') return s?.health;
    if (k === 'mana') return s?.mana;
    if (k === 'stamina') return s?.stamina;
    return null;
  });

  // Status dot color shown next to the podium icon:
  private _rankStatus(current: number | undefined, previous: number | undefined, hasPrevious: boolean): 'error' | 'success' | null {
    if (!hasPrevious) return null;
    if (current !== undefined && previous !== undefined) {
      if (current === previous) return null;
      return current < previous ? 'success' : 'error';
    }
    if (current === undefined && previous !== undefined) return 'error';
    if (current !== undefined && previous === undefined) return 'success';
    return null;
  }

  // Branches on `source()` to pull value + rank either from the favorite or the kingdom snapshot.
  private _resolve(entity: NonNullable<ChapterMeta['favorite'] | ChapterMeta['kingdom']>): RankedStatSnapshot {
    if (this.source() === 'kingdom') {
      const k = entity as NonNullable<ChapterMeta['kingdom']>;
      const key = this.stat();
      if (key === 'population') return this._snap(k.population.total, k.ranks.population);
      if (KINGDOM_META_STATS.has(key)) return this._snap(k.metadata[key as KingdomMetaStat], k.ranks[key as KingdomMetaStat]);
      const pk = key as 'housed_pct' | 'immortals' | 'infected' | 'nobles' | 'sick' | 'warriors';
      return this._snap(k.population[pk] ?? 0, k.ranks[pk]);
    }
    return this._resolveFavorite(entity as NonNullable<ChapterMeta['favorite']>);
  }

  // Per-kind field accessor — pulls value/rank from the favorite's stats/ranks dict.
  private _resolveFavorite(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    if (k === 'age') return this._snap(f.metadata.age, f.ranks_in_species.age);
    if (k === 'armor') return this._snap(f.stats.armor, f.ranks_in_species.armor);
    if (k === 'children') return this._snap(f.stats.children, f.ranks_in_species.children);
    if (k === 'attack_speed') return this._snap(f.stats.attack_speed, f.ranks_in_species.attack_speed);
    if (k === 'birth_rate') return this._snap(f.stats.birth_rate, f.ranks_in_species.birth_rate);
    if (k === 'critical_chance') return this._snap(f.stats.critical_chance, f.ranks_in_species.critical_chance);
    if (k === 'damage') return this._snap(f.stats.damage, f.ranks_in_species.damage);
    if (k === 'damage_range') return this._snap(f.stats.damage_range, f.ranks_in_species.damage_range);
    if (k === 'diplomacy') return this._snap(f.stats.diplomacy, f.ranks_in_species.diplomacy);
    if (k === 'equipment_power') return this._snap(f.stats.equipment_power, f.ranks_in_species.equipment_power);
    if (k === 'health') return this._snap(f.stats.health_max, f.ranks_in_species.health_max);
    if (k === 'intelligence') return this._snap(f.stats.intelligence, f.ranks_in_species.intelligence);
    if (k === 'kills') return this._snap(f.stats.kills, f.ranks_in_species.kills);
    if (k === 'level') return this._snap(f.stats.level, f.ranks_in_species.level);
    if (k === 'lifespan') return this._snap(f.stats.lifespan, f.ranks_in_species.lifespan);
    if (k === 'loot') return this._snap(f.stats.loot, f.ranks_in_species.loot);
    if (k === 'mana') return this._snap(f.stats.mana_max, f.ranks_in_species.mana_max);
    if (k === 'money') return this._snap(f.stats.money, f.ranks_in_species.money);
    if (k === 'renown') return this._snap(f.stats.renown, f.ranks_in_species.renown);
    if (k === 'speed') return this._snap(f.stats.speed, f.ranks_in_species.speed);
    if (k === 'stamina') return this._snap(f.stats.stamina_max, f.ranks_in_species.stamina_max);
    if (k === 'stewardship') return this._snap(f.stats.stewardship, f.ranks_in_species.stewardship);
    return this._snap(f.stats.warfare, f.ranks_in_species.warfare);
  }

  // Omits `rank` when undefined — required by `exactOptionalPropertyTypes`.
  private _snap(value: number, rank: number | undefined): RankedStatSnapshot {
    const out: RankedStatSnapshot = { value };
    if (rank !== undefined) out.rank = rank;
    return out;
  }

  // Picks the favorite or kingdom block from a chapter's meta based on the configured source.
  private _sourceOf(meta: ChapterMeta | undefined): ChapterMeta['favorite'] | ChapterMeta['kingdom'] {
    if (!meta) return null;
    return meta[this.source()];
  }

}

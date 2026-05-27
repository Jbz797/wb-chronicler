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

  public readonly deltaSuffix = input<string>('');
  public readonly hideDelta = input<boolean>(false);
  public readonly numberFormat = input<string>('1.0-0');
  public readonly showRank = input<boolean>(true);
  public readonly stat = input.required<RankedStatKind>();
  public readonly suffix = input<string>('');

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly data = computed(() => {
    const current = this._chronicler.currentChapter()?.meta.favorite;
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    if (!current) return null;

    const c = this._resolve(current);
    const p = previous ? this._resolve(previous) : null;

    const valueDelta = this.hideDelta() ? undefined : (p ? c.value - p.value : undefined);
    return { ...c, rankStatus: this._rankStatus(c.rank_in_species, p?.rank_in_species, !!p), valueDelta };
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

  // Per-kind field accessor — pulls value/rank from the favorite's stats/ranks dict.
  private _resolve(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    if (k === 'age') return this._snap(f.metadata.age, f.ranks_in_species.age);
    if (k === 'armor') return this._snap(f.stats.armor, f.ranks_in_species.armor);
    if (k === 'attack_speed') return this._snap(f.stats.attack_speed, f.ranks_in_species.attack_speed);
    if (k === 'birth_rate') return this._snap(f.stats.birth_rate, f.ranks_in_species.birth_rate);
    if (k === 'critical_chance') return this._snap(f.stats.critical_chance, f.ranks_in_species.critical_chance);
    if (k === 'damage') return this._snap(f.stats.damage, f.ranks_in_species.damage);
    if (k === 'damage_range') return this._snap(f.stats.damage_range, f.ranks_in_species.damage_range);
    if (k === 'diplomacy') return this._snap(f.stats.diplomacy, f.ranks_in_species.diplomacy);
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

  // Omits `rank_in_species` when undefined — required by `exactOptionalPropertyTypes`.
  private _snap(value: number, rankInSpecies: number | undefined): RankedStatSnapshot {
    const out: RankedStatSnapshot = { value };
    if (rankInSpecies !== undefined) out.rank_in_species = rankInSpecies;
    return out;
  }

}

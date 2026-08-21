import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { CITY_META_STATS, KINGDOM_META_STATS, NON_COMPACT_STATS } from '../../../constants';
import {
  ChapterMeta, CityMetaStat, KingdomAlliance, KingdomMetaStat, PeopleTier, PopulationStat, RankedStatKind, RankedStatSnapshot, SpeciesStanding, SpeciesTotals,
} from '../../../interfaces';
import { CompactPipe, ExactPipe, TierPipe } from '../../../pipes';
import { ChroniclerService } from '../../../services';
import { DeltaComponent } from '../delta/delta.component';

const peopleSources = new Set(['clan', 'culture', 'family', 'subspecies']); // the four tiers `_resolvePeople` serves, out of the if-chain to hold its complexity

@Component({
  selector: 'app-ranked-stat',
  imports: [CompactPipe, DecimalPipe, DeltaComponent, ExactPipe, TierPipe],
  templateUrl: './ranked-stat.component.html',
  styleUrl: './ranked-stat.component.scss',
})
export class RankedStatComponent {

  private readonly _chronicler = inject(ChroniclerService);

  public readonly deltaSuffix = input<string>('');
  public readonly hideDelta = input<boolean>(false);
  public readonly inverted = input<boolean>(false); // Flips the delta colour — for stats where a rise is bad (deaths).
  public readonly numberFormat = input<string>('1.0-0');
  public readonly showRank = input<boolean>(true);
  public readonly source = input<'alliance' | 'city' | 'clan' | 'culture' | 'family' | 'favorite' | 'kingdom' | 'species' | 'subspecies'>('favorite');
  public readonly stat = input.required<RankedStatKind>();
  public readonly suffix = input<string>('');

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
  // Kingdom/city/alliance quantities render compact (`X.X K` above 100), like the world panel — except age/`%`/per-capita stats.
  protected readonly useCompact = computed(() => this.source() !== 'favorite' && !NON_COMPACT_STATS.has(this.stat()));

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

  // Branches on `source()` to pull value + rank from the favorite, the kingdom/city snapshot, or the alliance.
  private _resolve(
    entity: KingdomAlliance | NonNullable<ChapterMeta['city'] | ChapterMeta['favorite'] | ChapterMeta['kingdom']> | PeopleTier | SpeciesStanding,
  ): RankedStatSnapshot {
    if (this.source() === 'alliance') {
      const a = entity as KingdomAlliance;
      const key = this.stat() as 'population' | 'renown';
      return this._snap(a[key], a.ranks?.[key]);
    }

    if (this.source() === 'city') return this._resolveCity(entity as NonNullable<ChapterMeta['city']>);

    // The stock a biology sprang from, ranked among the world's species rather than among its biologies — same two dicts as a people tier, minus `members`.
    if (this.source() === 'species') {
      const stock = entity as SpeciesStanding;
      const key = this.stat() as keyof SpeciesTotals;
      return this._snap(stock[key] ?? 0, stock.ranks?.[key]); // a count Python omits at 0 — a beast's stock holds no town — still reads as the zero it was
    }

    if (peopleSources.has(this.source())) return this._resolvePeople(entity as PeopleTier);

    if (this.source() === 'kingdom') {
      const k = entity as NonNullable<ChapterMeta['kingdom']>;
      const key = this.stat();

      if (key === 'score_rank') return this._snap(k.metadata.score_rank, undefined); // the value IS the placement — no podium rank of its own
      if (key === 'equipment') return this._snap(k.equipment.total, k.ranks?.equipment); // its own block: the racks ride alongside the total
      if (key === 'population') return this._snap(k.population.total, k.ranks?.population);

      // Score dimensions are omitted at 0 by Python, hence the `?? 0`.
      if (KINGDOM_META_STATS.has(key)) return this._snap(k.metadata[key as KingdomMetaStat] ?? 0, k.ranks?.[key as KingdomMetaStat]);

      const pk = key as PopulationStat;
      return this._snap(k.population[pk] ?? 0, k.ranks?.[pk]); // Only `immortals`/`infected`/`sick` can be absent — Python omits them at 0, so reading 0 is right.
    }
    return this._resolveFavorite(entity as NonNullable<ChapterMeta['favorite']>);
  }

  // Per-kind accessor for a city — `army`, `books`, `equipment` and `loyalty` each own a block, score dimensions sit in `metadata`, the rest in `population`.
  private _resolveCity(c: NonNullable<ChapterMeta['city']>): RankedStatSnapshot {
    const key = this.stat();

    if (key === 'score_rank') return this._snap(c.metadata.score_rank, undefined); // the value IS the placement — no podium rank of its own
    if (key === 'books') return this._snap(c.books.total, c.ranks?.books); // its own block: the volumes ride alongside the total
    if (key === 'equipment') return this._snap(c.equipment.total, c.ranks?.equipment); // its own block: the racks ride alongside the total
    if (key === 'loyalty') return this._snap(c.loyalty.total, c.ranks?.loyalty); // its own block, not `metadata`: the modifiers ride alongside the total
    if (key === 'population') return this._snap(c.population.total, c.ranks?.population);

    // Army stats rank under an `army_` prefix — the city already ranks `kills`/`deaths`/`renown` of its own. Only numeric fields are ever addressed this way.
    if (key.startsWith('army_')) {
      const army = c.army as unknown as Record<string, number | undefined> | undefined;
      return this._snap(army?.[key.slice(5)] ?? 0, (c.ranks as Record<string, number | undefined> | undefined)?.[key]);
    }

    // Score dimensions are omitted at 0 by Python, hence the `?? 0`.
    if (CITY_META_STATS.has(key)) return this._snap(c.metadata[key as CityMetaStat] ?? 0, c.ranks?.[key as CityMetaStat]);

    // The money ranks stay chronicler-only on both tiers, so a `nobles_money`/`subjects_money` lookup simply misses — the value still reads from `population`.
    const pk = key as PopulationStat;
    const ranks = c.ranks as Record<string, number | undefined> | undefined;
    return this._snap(c.population[pk] ?? 0, ranks?.[pk]);
  }

  // Per-kind field accessor — pulls value/rank from the favorite's stats/ranks dict.
  private _resolveFavorite(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    const ranks = f.ranks_in_species ?? {}; // Absent when the favorite tops nothing in its species — every lookup below then simply misses.
    if (k === 'age') return this._snap(f.metadata.age, ranks.age);
    if (k === 'armor') return this._snap(f.stats.armor, ranks.armor);
    if (k === 'children') return this._snap(f.stats.children, ranks.children);
    if (k === 'attack_speed') return this._snap(f.stats.attack_speed, ranks.attack_speed);
    if (k === 'critical_chance') return this._snap(f.stats.critical_chance, ranks.critical_chance);
    if (k === 'damage') return this._snap(f.stats.damage, ranks.damage);
    if (k === 'diplomacy') return this._snap(f.stats.diplomacy, ranks.diplomacy);
    if (k === 'equipment_power') return this._snap(f.stats.equipment_power, ranks.equipment_power);
    if (k === 'health') return this._snap(f.stats.health_max, ranks.health_max);
    if (k === 'intelligence') return this._snap(f.stats.intelligence, ranks.intelligence);
    if (k === 'kills') return this._snap(f.stats.kills, ranks.kills);
    if (k === 'level') return this._snap(f.stats.level, ranks.level);
    if (k === 'lifespan') return this._snap(f.stats.lifespan, ranks.lifespan);
    if (k === 'mana') return this._snap(f.stats.mana_max, ranks.mana_max);
    if (k === 'money') return this._snap(f.stats.money, ranks.money);
    if (k === 'renown') return this._snap(f.stats.renown, ranks.renown);
    if (k === 'speed') return this._snap(f.stats.speed, ranks.speed);
    if (k === 'stamina') return this._snap(f.stats.stamina_max, ranks.stamina_max);
    if (k === 'stewardship') return this._snap(f.stats.stewardship, ranks.stewardship);
    return this._snap(f.stats.warfare, ranks.warfare);
  }

  // A clan, a culture, a lineage, a biology, built alike: the body in `metadata`, its living in `population` as on a city, `members` apart. One podium for all.
  private _resolvePeople(entity: PeopleTier): RankedStatSnapshot {
    if (this.stat() === 'members') return this._snap(entity.members.total, entity.ranks?.members); // its own block, like a city's population
    const shelf = (entity as { books?: { total: number } }).books; // the culture alone carries one — its own block, as a town's library is
    if (shelf && this.stat() === 'books') return this._snap(shelf.total, (entity.ranks as Record<string, number | undefined> | undefined)?.books);
    const ranks = entity.ranks as Record<string, number | undefined> | undefined;
    const block = entity.population as unknown as Record<string, number | undefined>;
    const source = Object.hasOwn(block, this.stat()) ? block : (entity.metadata as unknown as Record<string, number | undefined>);
    return this._snap(source[this.stat()] ?? 0, ranks?.[this.stat()]); // WB omits a counter it never wrote, hence the `?? 0`
  }

  // Omits `rank` when undefined — required by `exactOptionalPropertyTypes`.
  private _snap(value: number, rank: number | undefined): RankedStatSnapshot {
    const out: RankedStatSnapshot = { value };
    if (rank !== undefined) out.rank = rank;
    return out;
  }

  // Picks the favorite, kingdom, city, or (nested) alliance block from a chapter's meta based on the configured source.
  private _sourceOf(
    meta: ChapterMeta | undefined,
  ): KingdomAlliance | NonNullable<ChapterMeta['city'] | ChapterMeta['favorite'] | ChapterMeta['kingdom']> | PeopleTier | SpeciesStanding | null {
    if (!meta) return null;
    if (this.source() === 'alliance') return meta.kingdom?.alliance ?? null;
    if (this.source() === 'species') return meta.subspecies?.species ?? null; // a section of the subspecies, where every other source is a chapter block
    return meta[this.source() as 'city' | 'clan' | 'culture' | 'family' | 'favorite' | 'kingdom' | 'subspecies'];
  }

}

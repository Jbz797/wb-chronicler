import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { CITY_META_STATS, FAVORITE_GAUGE_FIELDS, KINGDOM_META_STATS, NON_COMPACT_STATS } from '../../../../constants';
import {
  ChapterMeta, ChapterTier, CityMetaStat, KingdomAlliance, KingdomMetaStat, PeopleTier, PeopleTierName, PopulationStat, RankedStatKind, RankedStatSnapshot,
  RankedStatSource, SpeciesStanding, SpeciesTotals,
} from '../../../../interfaces';
import { CompactPipe, ExactPipe, TierPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { DeltaComponent } from '../delta/delta.component';

@Component({
  selector: 'app-ranked-stat',
  imports: [CompactPipe, DecimalPipe, DeltaComponent, ExactPipe, NzTooltipModule, TierPipe],
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
  public readonly source = input<RankedStatSource>('favorite');
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

  // A `Record` rather than a bare list: a tier added to `PeopleTierName` breaks the build here instead of quietly falling through to the favourite's resolver.
  private readonly _peopleSources: Record<PeopleTierName, true> = { clan: true, culture: true, family: true, language: true, religion: true, subspecies: true };

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

    if (Object.hasOwn(this._peopleSources, this.source())) return this._resolvePeople(entity as PeopleTier);

    if (this.source() === 'kingdom') {
      const k = entity as NonNullable<ChapterMeta['kingdom']>;
      const key = this.stat();

      if (key === 'score_rank') return this._snap(k.metadata.score_rank, undefined); // the value IS the placement — no podium rank of its own
      if (key === 'boats') return this._snap(k.boats.total, k.ranks?.boats); // its own block: the hulls ride alongside the total
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

    // Army stats rank under an `army_` prefix, the city ranking `kills`/`deaths`/`renown` of its own. The corps also holds a name and a captain: hence the typeof.
    if (key.startsWith('army_')) {
      const value = c.army?.[key.slice(5) as keyof NonNullable<typeof c.army>];
      return this._snap(typeof value === 'number' ? value : 0, c.ranks?.[key as keyof NonNullable<typeof c.ranks>]);
    }

    // Score dimensions are omitted at 0 by Python, hence the `?? 0`.
    if (CITY_META_STATS.has(key)) return this._snap(c.metadata[key as CityMetaStat] ?? 0, c.ranks?.[key as CityMetaStat]);

    // The money ranks stay chronicler-only on both tiers, so a `nobles_money`/`subjects_money` lookup simply misses — the value still reads from `population`.
    const pk = key as PopulationStat;
    const ranks = c.ranks as Record<string, number | undefined> | undefined;
    return this._snap(c.population[pk] ?? 0, ranks?.[pk]);
  }

  // Per-kind accessor over the favorite's stats/ranks. A stat WB never wrote is one nothing granted — no weapon to crit with — so absent reads as zero.
  private _resolveFavorite(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    const ranks = f.ranks_in_species ?? {}; // Absent when the favorite tops nothing in its species — every lookup below then simply misses.
    if (k === 'age') return this._snap(f.metadata.age, ranks.age); // the one kind read off `metadata`; every other names a field of `stats`
    const field = FAVORITE_GAUGE_FIELDS[k] ?? k;
    return this._snap(f.stats[field as keyof typeof f.stats] ?? 0, ranks[field as keyof typeof ranks]);
  }

  // A clan, a culture, a lineage, a tongue, a biology, built alike: the body in `metadata`, its living in `population` as on a city, the roster apart.
  private _resolvePeople(entity: PeopleTier): RankedStatSnapshot {
    const ranks = entity.ranks as Record<string, number | undefined> | undefined;
    const key = this.stat();
    // Its own block, like a city's population, and named alike on every tier — a tongue's speakers answer to `members` as a clan's kin do.
    if (key === 'members') return this._snap(entity.members?.total ?? 0, ranks?.members);
    const shelf = (entity as { books?: { total: number } }).books; // a custom and a tongue each carry one — its own block, as a town's library is
    if (shelf && key === 'books') return this._snap(shelf.total, ranks?.books);
    // Its living first, its body second. `metadata` also holds names and refs, so the count is what a number proves it to be — WB omits one it never wrote.
    const { metadata, population } = entity;
    const held = Object.hasOwn(population, key) ? population[key as keyof typeof population] : metadata[key as keyof typeof metadata];
    return this._snap(typeof held === 'number' ? held : 0, ranks?.[key]);
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
    return meta[this.source() as ChapterTier];
  }

}

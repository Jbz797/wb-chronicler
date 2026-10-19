import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslateService } from '@ngx-translate/core';

import { CITY_META_STATS, FAVORITE_GAUGE_FIELDS, KINGDOM_META_STATS, NON_COMPACT_STATS } from '../../../../constants';
import { NumberHelpers } from '../../../../helpers';
import {
  ChapterMeta, ChapterTier, CityMetaStat, KingdomMetaStat, PeopleTier, PeopleTierName, PopulationStat, RankedStatKind, RankedStatSnapshot,
  RankedStatSource, SpeciesStanding, SpeciesTotals,
} from '../../../../interfaces';
import { CompactPipe, ExactPipe, TierPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { DeltaComponent } from '../delta/delta.component';
import { NewBadgeComponent } from '../new-badge/new-badge.component';

@Component({
  selector: 'app-ranked-stat',
  imports: [CompactPipe, DecimalPipe, DeltaComponent, ExactPipe, NewBadgeComponent, NzTooltipModule, TierPipe],
  templateUrl: './ranked-stat.component.html',
  styleUrl: './ranked-stat.component.scss',
})
export class RankedStatComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _translate = inject(TranslateService);

  public readonly deltaSuffix = input<string>('');
  public readonly hideDelta = input<boolean>(false);
  public readonly inverted = input<boolean>(false); // Flips the delta colour — for stats where a rise is bad (deaths).
  public readonly numberFormat = input<string>('1.0-0');
  public readonly ordinal = input<boolean>(false); // A placement rather than a count: the mark it wears is the number's own, and the tongue's.
  public readonly rankHint = input<string>(''); // An i18n key, said over the medal where its field is not the one the panel's others are ranked in.
  public readonly showRank = input<boolean>(true);
  public readonly source = input<RankedStatSource>('favorite');
  public readonly stat = input.required<RankedStatKind>();
  public readonly suffix = input<string>(''); // An i18n key, resolved below — the unit rides with the figure, so it turns with the rest.

  protected readonly data = computed(() => {
    const current = this._sourceOf(this._chronicler.currentChapter()?.meta);
    if (!current) return null;

    // A body the chapter before did not name, or named as another, leaves nothing to compare: its figures are a stranger's.
    const tier = this.source() === 'species' ? 'subspecies' : (this.source() as ChapterTier);
    const previous = this._chronicler.carriesOver(tier) ? this._sourceOf(this._chronicler.previousChapter()?.meta) : null;
    const c = this._resolve(current);
    const p = previous ? this._resolve(previous) : null;

    // Python drops a figure at 0, so a body's line absent last chapter reads 0 there: a figure that appears is new, not a rise from nothing.
    const isNew = !!p && p.value === 0 && c.value !== 0;
    const valueDelta = isNew || this.hideDelta() ? undefined : (p ? c.value - p.value : undefined);
    return { ...c, isNew, rankStatus: this._rankStatus(c.rank, p?.rank, !!p), valueDelta };
  });
  // Live gauge value for stats that have a cap (health/mana/stamina). `null` for all others.
  protected readonly gaugeValue = computed(() => {
    const k = this.stat();
    const s = this._chronicler.currentChapter()?.meta.favorite?.stats;
    if (k === 'health') return s?.health;
    if (k === 'mana') return s?.mana;
    return k === 'stamina' ? s?.stamina : null;
  });
  // The medal's field in words, where one was named — nothing otherwise, and the tooltip then stays shut.
  protected readonly hint = computed(() => {
    const key = this.rankHint();
    return key ? (this._translate.instant(key) as string) : '';
  });
  // The unit printed after the figure: an ordinal takes the placement's own mark, anything else its translated word. Nothing asked for, nothing printed.
  protected readonly unit = computed(() => {
    if (this.ordinal()) return NumberHelpers.ordinal(this.data()?.value ?? 0, this._translate.currentLang() !== 'en');
    const key = this.suffix();
    return key ? (this._translate.instant(key) as string) : '';
  });
  // Kingdom/city/alliance quantities render compact (`X.X K` above 100), like the world panel — except age/`%`/per-capita stats.
  protected readonly useCompact = computed(() => this.source() !== 'favorite' && !NON_COMPACT_STATS.has(this.stat()));

  // A `Record` rather than a bare list: a tier added to `PeopleTierName` breaks the build here instead of quietly falling through to the favourite's resolver.
  private readonly _peopleSources: Record<PeopleTierName, true> = {
    alliance: true, clan: true, culture: true, family: true, language: true, religion: true, subspecies: true,
  };

  // Status dot color shown next to the podium icon:
  private _rankStatus(current: number | undefined, previous: number | undefined, hasPrevious: boolean): 'error' | 'success' | null {
    if (!hasPrevious) return null;
    if (current !== undefined && previous !== undefined) {
      if (current === previous) return null;
      return current < previous ? 'success' : 'error';
    }
    if (current === undefined && previous !== undefined) return 'error';
    return current !== undefined && previous === undefined ? 'success' : null;
  }

  // Branches on `source()` to pull value + rank from the favorite, the kingdom/city snapshot, or any body that rosters the living — the pact included.
  private _resolve(
    entity: NonNullable<ChapterMeta['city'] | ChapterMeta['favorite'] | ChapterMeta['kingdom']> | PeopleTier | SpeciesStanding,
  ): RankedStatSnapshot {
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

      if (key === 'score_rank') return this._snap(k.metadata.score_rank ?? 0, undefined); // the value IS the placement — no podium rank of its own
      if (key === 'boats') return this._snap(k.boats?.total ?? 0, k.ranks?.boats); // its own block: the hulls ride alongside the total
      if (key === 'gear') return this._snap(k.gear?.total ?? 0, k.ranks?.gear); // its own block: the racks ride alongside the total
      if (key === 'pop') return this._snap(k.pop.total, k.ranks?.pop);

      // Score dimensions are omitted at 0 by Python, hence the `?? 0`.
      if (KINGDOM_META_STATS.has(key)) return this._snap(k.metadata[key as KingdomMetaStat] ?? 0, k.ranks?.[key as KingdomMetaStat]);

      const pk = key as PopulationStat;
      // Only `immortals`/`infected`/`sick` go missing on the value side, omitted at 0 — the rank side is widened instead, `fed_pct` holding a share ranked nowhere.
      const ranks = k.ranks as unknown as Record<string, number | undefined> | undefined;
      return this._snap(k.pop[pk] ?? 0, ranks?.[pk]);
    }
    return this._resolveFavorite(entity as NonNullable<ChapterMeta['favorite']>);
  }

  // Per-kind accessor for a city — `army`, `books`, `buildings`, `gear`, `loyalty` each own a block, score dimensions sit in `metadata`, the rest in `pop`.
  private _resolveCity(c: NonNullable<ChapterMeta['city']>): RankedStatSnapshot {
    const key = this.stat();

    if (key === 'score_rank') return this._snap(c.metadata.score_rank ?? 0, undefined); // the value IS the placement — no podium rank of its own
    // Each its own block, not `metadata`: the volumes, the racks, the modifiers ride alongside the total — and the block goes whole at nought.
    if (key === 'books' || key === 'buildings' || key === 'gear' || key === 'loyalty') return this._snap(c[key]?.total ?? 0, c.ranks?.[key]);
    if (key === 'pop') return this._snap(c.pop.total, c.ranks?.pop);

    // Army stats rank under an `army_` prefix, the city ranking `kills`/`deaths`/`renown` of its own. The corps also holds a name and a captain: hence the typeof.
    if (key.startsWith('army_')) {
      const value = c.army?.[key.slice(5) as keyof NonNullable<typeof c.army>];
      return this._snap(typeof value === 'number' ? value : 0, c.ranks?.[key as keyof NonNullable<typeof c.ranks>]);
    }

    // Score dimensions are omitted at 0 by Python, hence the `?? 0`.
    if (CITY_META_STATS.has(key)) return this._snap(c.metadata[key as CityMetaStat] ?? 0, c.ranks?.[key as CityMetaStat]);

    // The money ranks stay chronicler-only on both tiers, so a money share's lookup simply misses — the value still reads from `pop`.
    const pk = key as PopulationStat;
    const ranks = c.ranks as Record<string, number | undefined> | undefined;
    return this._snap(c.pop[pk] ?? 0, ranks?.[pk]);
  }

  // Per-kind accessor over the favorite's stats/ranks. A stat WB never wrote is one nothing granted — no weapon to crit with — so absent reads as zero.
  private _resolveFavorite(f: NonNullable<ChapterMeta['favorite']>): RankedStatSnapshot {
    const k = this.stat();
    const ranks = f.ranks_in_species ?? {}; // Absent when the favorite tops nothing in its species — every lookup below then simply misses.
    if (k === 'age') return this._snap(f.metadata.age, ranks.age); // read off `metadata`, as the post's years are; every other names a field of `stats`
    if (k === 'tenure_years') return this._snap(f.metadata.tenure_years ?? 0, f.metadata.tenure_rank_in_post); // ranked among the post's holders, not the species
    const field = FAVORITE_GAUGE_FIELDS[k] ?? k;
    // `level` alone has a floor of 1, where Python leaves it unsaid.
    return this._snap(f.stats[field as keyof typeof f.stats] ?? (field === 'level' ? 1 : 0), ranks[field as keyof typeof ranks]);
  }

  // A clan, a culture, a family, a tongue, a biology, built alike: the body in `metadata`, its living in `pop` as on a city, the roster apart.
  private _resolvePeople(entity: PeopleTier): RankedStatSnapshot {
    const ranks = entity.ranks as Record<string, number | undefined> | undefined;
    const key = this.stat();
    // The pact gathers rather than enrols, so its head-count sits in `pop.total` as a town's and a crown's do, not under `members`.
    if (key === 'pop') return this._snap(entity.pop?.total ?? 0, ranks?.pop);
    const shelf = (entity as { books?: { total: number } }).books; // a custom and a tongue each carry one — its own block, as a town's library is
    if (shelf && key === 'books') return this._snap(shelf.total, ranks?.books);
    // Its living first, its body second. `metadata` also holds names and refs, so the count is what a number proves it to be — WB omits one it never wrote.
    const { metadata, pop = {} } = entity;
    const held = Object.hasOwn(pop, key) ? pop[key as keyof typeof pop] : metadata[key as keyof typeof metadata];
    return this._snap(typeof held === 'number' ? held : 0, ranks?.[key]);
  }

  // Omits `rank` when undefined — required by `exactOptionalPropertyTypes`.
  private readonly _snap = (value: number, rank: number | undefined): RankedStatSnapshot => rank === undefined ? { value } : { rank, value };

  // Picks the favorite, the kingdom, the city, or any tier block from a chapter's meta based on the configured source.
  private _sourceOf(
    meta: ChapterMeta | undefined,
  ): NonNullable<ChapterMeta['city'] | ChapterMeta['favorite'] | ChapterMeta['kingdom']> | PeopleTier | SpeciesStanding | null {
    if (!meta) return null;
    // A section of the subspecies, where every other source is a chapter block.
    return this.source() === 'species' ? (meta.subspecies?.species ?? null) : (meta[this.source() as ChapterTier] ?? null);
  }

}

import { Component, computed, inject } from '@angular/core';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { COMBAT_STATS, PERSONALITY_LABELS, ROLE_LABELS, SKILL_STATS } from '../../../../constants';
import { RarityCounts } from '../../../../interfaces';
import { TierPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services/chronicler.service';
import { RankedStatComponent, RarityStatsComponent } from '../../../misc';

import { CompanionCardComponent } from './companion-card/companion-card.component';
import { PlotCardComponent } from './plot-card/plot-card.component';

@Component({
  selector: 'app-favorite',
  imports: [
    CompanionCardComponent,
    NzBadgeModule,
    NzDescriptionsModule,
    NzEmptyModule,
    NzTagModule,
    PlotCardComponent,
    RankedStatComponent,
    RarityStatsComponent,
    TierPipe,
  ],
  templateUrl: './favorite.component.html',
})
export class FavoriteComponent {

  protected readonly combatStats = COMBAT_STATS;
  protected readonly skillStats = SKILL_STATS;

  private readonly _chronicler = inject(ChroniclerService);

  protected currentChapter = this._chronicler.currentChapter;

  // Children counter formatted for the template — appends "(N naissances)" only when total births exceed living children.
  protected readonly childrenLabel = computed(() => {
    const s = this.currentChapter()?.meta.favorite?.stats;
    if (!s) return '';
    let label = `${s.children} / ${s.max_children}`;
    if (s.births !== s.children) label += ` (${s.births} naissances)`;
    return label;
  });
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
      equipment: diffCounts(current.equipment, previous.equipment),
      traits: diffCounts(current.traits, previous.traits),
    };
  });
  // Tags: personality + active roles. Each one carries `isNew` (true if absent from the previous chapter).
  protected readonly roleTags = computed(() => {
    const meta = this.currentChapter()?.meta.favorite?.metadata;
    if (!meta) return [];

    const previousMeta = this._chronicler.previousChapter()?.meta.favorite?.metadata;
    const previousRoles = new Set(previousMeta?.roles);
    const tags: { color: string; isNew: boolean; label: string }[] = [];

    if (meta.personality) {
      const isNew = !!previousMeta && previousMeta.personality !== meta.personality;
      tags.push({ color: 'magenta', isNew, label: PERSONALITY_LABELS[meta.personality] ?? meta.personality });
    }

    for (const role of meta.roles) {
      const definition = ROLE_LABELS[role];
      if (definition?.active) {
        const isNew = !!previousMeta && !previousRoles.has(role);
        tags.push({ color: 'blue', isNew, label: definition.label });
      }
    }

    return tags;
  });
  protected readonly hasNewRole = computed(() => this.roleTags().some(tag => tag.isNew));
  // Flatten the inventory dict into a list for the template — Python emits it already sorted alphabetically.
  protected readonly inventoryEntries = computed(() => {
    const inv = this.currentChapter()?.meta.favorite?.inventory ?? {};
    return Object.entries(inv).map(([key, amount]) => ({ amount, key }));
  });
  protected readonly isNewDescriptor = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    const current = this.currentChapter()?.meta.favorite?.descriptor;
    return !!previous && current !== undefined && current !== previous.descriptor;
  });

}

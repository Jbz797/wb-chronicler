import { Component, computed, inject } from '@angular/core';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { COMBAT_STATS, LIFE_STAGE_LABELS, PERSONALITY_LABELS, ROLE_LABELS, SKILL_STATS, TENURE_LABELS } from '../../../../constants';
import { RarityCounts } from '../../../../interfaces';
import { TierPipe } from '../../../../pipes';
import { ChroniclerService } from '../../../../services';
import { NewBadgeComponent, RankedStatComponent, RarityStatsComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';

import { PlotCardComponent } from './plot-card/plot-card.component';

@Component({
  selector: 'app-favorite',
  imports: [
    NewBadgeComponent,
    NzBadgeModule,
    NzDescriptionsModule,
    NzTagModule,
    PersonTagComponent,
    PlotCardComponent,
    RankedStatComponent,
    RarityStatsComponent,
    TierPipe,
  ],
  templateUrl: './favorite.component.html',
})
export class FavoriteComponent {

  private readonly _chronicler = inject(ChroniclerService);

  protected readonly combatStats = COMBAT_STATS;
  protected readonly skillStats = SKILL_STATS;

  protected currentChapter = this._chronicler.currentChapter;

  // Age suffix « ans (<stage>) » — appends the life-stage label to the ranked age value.
  protected readonly ageSuffix = computed(() => {
    const stage = this.currentChapter()?.meta.favorite?.metadata.life_stage;
    return stage ? ` ans (${LIFE_STAGE_LABELS[stage]})` : ' ans';
  });
  // Tags: personality + active roles. Each one carries `isNew` (true if absent from the previous chapter).
  protected readonly roleTags = computed(() => {
    const meta = this.currentChapter()?.meta.favorite?.metadata;
    if (!meta) return [];

    const previousMeta = this._chronicler.previousChapter()?.meta.favorite?.metadata;
    const previousRoles = new Set(previousMeta?.roles);
    const roles = meta.roles ?? []; // Absent when the favorite holds none — `emit` strips the empty list.
    const tags: { color: string; isNew: boolean; label: string }[] = [];

    if (meta.personality) {
      const isNew = !!previousMeta && previousMeta.personality !== meta.personality;
      tags.push({ color: 'yellow', isNew, label: PERSONALITY_LABELS[meta.personality] ?? meta.personality });
    }

    for (const role of roles) {
      const definition = ROLE_LABELS[role];
      if (definition?.active) {
        const isNew = !!previousMeta && !previousRoles.has(role);
        tags.push({ color: 'lime', isNew, label: definition.label });
      }
    }

    return tags;
  });
  // Changed-since-previous flags — centralizes all NEW badge conditions for this component.
  protected readonly changedFields = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    const current = this.currentChapter()?.meta.favorite;
    if (!previous || !current) return { bestFriend: false, descriptor: false, lover: false, plot: false, role: false };

    let hasPlotChanged = false;
    if (current.plot) hasPlotChanged = previous.plot ? previous.plot.type_id !== current.plot.type_id : true;

    return {
      bestFriend: !!current.companions?.best_friend && current.companions.best_friend.id !== previous.companions?.best_friend?.id,
      descriptor: current.descriptor !== previous.descriptor,
      lover: !!current.companions?.lover && current.companions.lover.id !== previous.companions?.lover?.id,
      plot: hasPlotChanged,
      role: this.roleTags().some(tag => tag.isNew),
    };
  });
  // The attachments the favorite actually has — an absent one drops its row entirely, so the template needs neither a fallback nor a branch to render one.
  protected readonly companionRows = computed(() => {
    const companions = this.currentChapter()?.meta.favorite?.companions;
    const changed = this.changedFields();
    return [
      { isNew: changed.lover, label: 'Amoureux', person: companions?.lover },
      { isNew: changed.bestFriend, label: 'Meilleur ami', person: companions?.best_friend },
    ].flatMap(row => row.person ? [{ ...row, person: row.person }] : []);
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

    return { traits: diffCounts(current.traits, previous.traits) };
  });
  // Flatten the inventory dict into a list for the template — Python emits it already sorted alphabetically.
  protected readonly inventoryEntries = computed(() => {
    const inv = this.currentChapter()?.meta.favorite?.inventory ?? {};
    return Object.entries(inv).map(([key, amount]) => ({ amount, key }));
  });
  // Names the post `tenure_years` counts — only kings/leaders/captains hold one, so the fallback never surfaces.
  protected readonly tenureLabel = computed(() => TENURE_LABELS[this.currentChapter()?.meta.favorite?.metadata.profession ?? ''] ?? 'Ancienneté');

}

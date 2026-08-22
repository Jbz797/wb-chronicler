import { Component, computed, inject } from '@angular/core';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { COMBAT_STATS, COMPANION_LABELS, LIFE_STAGE_LABELS, PERSONALITY_LABELS, ROLE_LABELS, SKILL_STATS, TENURE_LABELS } from '../../../../constants';
import { LabelHelpers } from '../../../../helpers';
import { RarityCounts } from '../../../../interfaces';
import { TierPipe } from '../../../../pipes';
import { ChroniclerService, RegistryService } from '../../../../services';
import { InventoryComponent, NewBadgeComponent, RankedStatComponent, RarityStatsComponent } from '../../../misc';
import { PersonTagComponent } from '../../../tags';

import { BoatCardComponent } from './boat-card/boat-card.component';
import { PlotCardComponent } from './plot-card/plot-card.component';

@Component({
  selector: 'app-favorite',
  imports: [
    BoatCardComponent,
    InventoryComponent,
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
  private readonly _registry = inject(RegistryService);

  protected readonly combatStats = COMBAT_STATS;
  protected readonly skillStats = SKILL_STATS;

  protected currentChapter = this._chronicler.currentChapter;

  // Age suffix « ans (<stage>) » — appends the life-stage label to the ranked age value.
  protected readonly ageSuffix = computed(() => {
    const meta = this.currentChapter()?.meta.favorite?.metadata;
    return meta?.life_stage ? ` ans (${LabelHelpers.gendered(LIFE_STAGE_LABELS[meta.life_stage], meta.sex)})` : ' ans';
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
      tags.push({ color: 'yellow', isNew, label: LabelHelpers.gendered(PERSONALITY_LABELS[meta.personality], meta.sex) || meta.personality });
    }

    for (const role of roles) {
      const definition = ROLE_LABELS[role];
      if (definition?.active) {
        const isNew = !!previousMeta && !previousRoles.has(role);
        tags.push({ color: 'lime', isNew, label: LabelHelpers.gendered(definition.label, meta.sex) });
      }
    }

    return tags;
  });
  // Changed-since-previous flags — centralizes all NEW badge conditions for this component.
  protected readonly changedFields = computed(() => {
    const previous = this._chronicler.previousChapter()?.meta.favorite;
    const current = this.currentChapter()?.meta.favorite;
    const isBoarded = !!this.currentChapter()?.meta.boat && !this._chronicler.previousChapter()?.meta.boat; // he sails now and did not before
    if (!previous || !current) return { bestFriend: false, boat: isBoarded, descriptor: false, lover: false, plot: false, role: false };

    let hasPlotChanged = false;
    if (current.plot) hasPlotChanged = previous.plot ? previous.plot.type.id !== current.plot.type.id : true;

    return {
      bestFriend: !!current.companions?.best_friend && current.companions.best_friend.id !== previous.companions?.best_friend?.id,
      boat: isBoarded,
      descriptor: current.descriptor !== previous.descriptor,
      lover: !!current.companions?.lover && current.companions.lover.id !== previous.companions?.lover?.id,
      plot: hasPlotChanged,
      role: this.roleTags().some(tag => tag.isNew),
    };
  });
  // An absent attachment drops its row, sparing the template a fallback. Labels agree with the companion, whose sex only the registry holds — the ref is id + name.
  protected readonly companionRows = computed(() => {
    const companions = this.currentChapter()?.meta.favorite?.companions;
    const changed = this.changedFields();
    const persons = this._registry.persons();
    return [
      { icon: 'lovers', isNew: changed.lover, label: COMPANION_LABELS.lover, person: companions?.lover },
      { icon: 'friendship', isNew: changed.bestFriend, label: COMPANION_LABELS.best_friend, person: companions?.best_friend },
    ].flatMap((row) => {
      if (!row.person) return [];
      return [{ ...row, label: LabelHelpers.gendered(row.label, persons[String(row.person.id)]?.sex), person: row.person }];
    });
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
  // Names the post `tenure_years` counts — only kings/leaders/captains hold one, so the fallback never surfaces.
  protected readonly tenureLabel = computed(() => TENURE_LABELS[this.currentChapter()?.meta.favorite?.metadata.job ?? ''] ?? 'Ancienneté');

}

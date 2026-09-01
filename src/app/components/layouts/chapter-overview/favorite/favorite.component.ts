import { Component, computed, inject } from '@angular/core';

import { NzBadgeModule } from 'ng-zorro-antd/badge';
import { NzDescriptionsModule } from 'ng-zorro-antd/descriptions';
import { NzTagModule } from 'ng-zorro-antd/tag';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { InventoryComponent, NewBadgeComponent, RankedStatComponent, TraitSummaryComponent } from '..';
import { ACTIVE_ROLES, COMBAT_STATS, SKILL_STATS } from '../../../../constants';
import { LabelHelpers } from '../../../../helpers';
import { TierPipe } from '../../../../pipes';
import { ChroniclerService, RegistryService } from '../../../../services';
import { PersonTagComponent } from '../tags';

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
    TierPipe,
    TraitSummaryComponent,
    TranslatePipe,
  ],
  templateUrl: './favorite.component.html',
})
export class FavoriteComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _registry = inject(RegistryService);
  private readonly _translate = inject(TranslateService);

  protected readonly combatStats = COMBAT_STATS;
  protected readonly skillStats = SKILL_STATS;

  protected currentChapter = this._chronicler.currentChapter;

  // Age suffix « ans (<stage>) » — appends the life-stage label to the ranked age value.
  protected readonly ageSuffix = computed(() => {
    const meta = this.currentChapter()?.meta.favorite?.metadata;
    return meta?.life_stage ? ` ans (${LabelHelpers.gendered(this._translate, `life_stage_${meta.life_stage}`, meta.sex)})` : ' ans';
  });
  // Tags: personality + active roles. Each one carries `isNew` (true if absent from the previous chapter).
  protected readonly roleTags = computed(() => {
    const meta = this.currentChapter()?.meta.favorite?.metadata;
    if (!meta) return [];

    const previousMeta = this._chronicler.carriesOver('favorite') ? this._chronicler.previousChapter()?.meta.favorite?.metadata : undefined;
    const previousRoles = new Set(previousMeta?.roles);
    const roles = meta.roles ?? []; // Absent when the favorite holds none — `emit` strips the empty list.
    const tags: { color: string; isNew: boolean; label: string }[] = [];

    if (meta.personality) {
      const isNew = !!previousMeta && previousMeta.personality !== meta.personality;
      tags.push({ color: 'yellow', isNew, label: LabelHelpers.gendered(this._translate, `personality_${meta.personality}`, meta.sex) || meta.personality });
    }

    // Only a post still held earns its tag; a founding is the chronicle's to tell, not the panel's.
    const held = roles.filter(role => ACTIVE_ROLES.has(role));
    for (const role of held) {
      const isNew = !!previousMeta && !previousRoles.has(role);
      tags.push({ color: 'lime', isNew, label: LabelHelpers.gendered(this._translate, `role_${role}`, meta.sex) });
    }

    return tags;
  });
  // Changed-since-previous flags — centralizes all NEW badge conditions for this component.
  protected readonly changedFields = computed(() => {
    const previous = this._chronicler.carriesOver('favorite') ? this._chronicler.previousChapter()?.meta.favorite : undefined;
    const current = this.currentChapter()?.meta.favorite;
    // A successor aboard is not a man who has taken to the sea — the hull is only news against the same soul's last landfall.
    const isBoarded = !!previous && !!this.currentChapter()?.meta.boat && !this._chronicler.previousChapter()?.meta.boat;
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
      { icon: 'lovers', isNew: changed.lover, key: 'companion_lover', person: companions?.lover },
      { icon: 'friendship', isNew: changed.bestFriend, key: 'companion_best_friend', person: companions?.best_friend },
    ].flatMap((row) => {
      if (!row.person) return [];
      return [{ ...row, label: LabelHelpers.gendered(this._translate, row.key, persons[String(row.person.id)]?.sex), person: row.person }];
    });
  });
  // Names the post `tenure_years` counts — only kings/leaders/captains hold one, so the fallback never surfaces.
  protected readonly tenureLabel = computed(() => {
    const key = `tenure_${this.currentChapter()?.meta.favorite?.metadata.job ?? ''}`;
    const label = this._translate.instant(key) as string;
    return label === key ? (this._translate.instant('tenure_default') as string) : label;
  });

}

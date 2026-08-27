import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzModalRef } from 'ng-zorro-antd/modal';
import { NzRadioModule } from 'ng-zorro-antd/radio';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { NgScrollbarModule } from 'ngx-scrollbar';

import { SAVES_ENDPOINT, SETTINGS_ENDPOINT, SETTINGS_FILE } from '../../../constants';
import { SaveCandidate, Settings } from '../../../interfaces';

const customValue = 'custom'; // the radio's own value, standing for « somewhere else » — never a path

@Component({
  selector: 'app-settings',
  imports: [DatePipe, DecimalPipe, FormsModule, NgScrollbarModule, NzAlertModule, NzButtonModule, NzDividerModule, NzInputModule, NzRadioModule, NzTooltipModule],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {

  private readonly _message = inject(NzMessageService);
  private readonly _modal = inject(NzModalRef);

  public readonly unreachable = signal(false);

  protected readonly candidates = signal<SaveCandidate[]>([]);
  protected readonly custom = signal('');
  protected readonly customValue = customValue;
  protected readonly picked = signal('');

  // `custom` is the radio's own value: an empty box means the reader has yet to say where, so nothing is offered to save.
  public chosen = (): string => this.picked() === customValue ? this.custom().trim() : this.picked();

  // Two sources, since only one of them needs the service: it alone can walk the disk for slots, where the recorded path is an asset like any other.
  public async load(): Promise<void> {
    try {
      const [slots, recorded] = await Promise.all([fetch(SAVES_ENDPOINT), fetch(SETTINGS_FILE)]);
      const settings = recorded.ok ? ((await recorded.json()) as Settings) : {}; // 404 on a first run, and after a new game wipes it
      this._apply((await slots.json()) as SaveCandidate[], settings.savePath ?? '');
    } catch {
      this.unreachable.set(true);
    }
  }

  // The service checks the path exists first — a wrong one would surface much later, in the chronicler's tooling. Its promise drives the footer's `autoLoading`.
  public async submit(): Promise<void> {
    const savePath = this.chosen();
    if (!savePath) return;

    try {
      const answer = await fetch(SETTINGS_ENDPOINT, { body: JSON.stringify({ savePath }), headers: { 'content-type': 'application/json' }, method: 'POST' });
      if (!answer.ok) throw new Error(String(answer.status));
      this._message.success('Sauvegarde WorldBox enregistrée');
      this._modal.close(savePath);
    } catch {
      this._message.error(`Chemin introuvable : ${savePath}`);
    }
  }

  // WorldBox keeps its automatic saves in a folder of their own, next to the manual ones — only a hand-typed path can land there, and only by mistake.
  protected isAutosave = (): boolean => /[/\\]autosaves[/\\]/.test(this.chosen());

  protected isCustom = (): boolean => this.picked() === customValue;

  // Every slot shares the same WorldBox folder and the same file name: its own two segments are all that tells them apart, the full path riding in a tooltip.
  protected shortPath = (savePath: string): string => savePath.split(/[/\\]/).slice(-3, -1).join('/');

  // What was already on record wins; failing that, the slot written last — most often the one the player has just left.
  private _apply(candidates: SaveCandidate[], recorded: string): void {
    this.candidates.set(candidates);
    const isKnown = candidates.some(candidate => candidate.path === recorded);
    if (recorded && !isKnown) this.custom.set(recorded);
    const fallback = recorded ? customValue : candidates[0]?.path ?? customValue;
    this.picked.set(isKnown ? recorded : fallback);
  }

}

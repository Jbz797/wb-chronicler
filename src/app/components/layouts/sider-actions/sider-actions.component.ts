import { HttpClient } from '@angular/common/http';
import { Component, inject } from '@angular/core';

import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { catchError, of } from 'rxjs';

import { RESET_ENDPOINT, SETTINGS_FILE } from '../../../constants';
import { Settings } from '../../../interfaces';
import { ChroniclerService } from '../../../services';
import { SettingsComponent } from '../settings/settings.component';

@Component({
  selector: 'app-sider-actions',
  imports: [NzButtonModule, NzModalModule, NzTooltipModule],
  templateUrl: './sider-actions.component.html',
  styleUrl: './sider-actions.component.scss',
})
export class SiderActionsComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _http = inject(HttpClient);
  private readonly _modal = inject(NzModalService);

  protected chapters = this._chronicler.chapters;

  constructor() {
    this._openSettingsIfUnset();
  }

  // Nothing is undone from here, so the count is spelled out and the confirm button says what it does rather than "OK".
  protected confirmNewGame = (): void => {
    const count = this.chapters().length;
    this._modal.confirm({
      nzCancelText: 'Annuler',
      nzContent: `Les ${count} chapitres seront effacés, avec l'identité du monde, les lieux que le chroniqueur a nommés et l'historique cumulatif du jeu. `
        + 'Cette suppression est définitive. '
        + 'Il faudra ensuite ouvrir une nouvelle session du chroniqueur : celle en cours garde en mémoire un monde qui n’existera plus.',
      nzOkDanger: true,
      nzOkText: 'Tout effacer',
      nzOnOk: () => this._wipe(),
      nzTitle: 'Repartir de zéro ?',
    });
  };

  // Opened from the button, and on its own at startup while no save is on record — without one the chronicler has nothing to read.
  protected openSettings = (): void => {
    const modal = this._modal.create<SettingsComponent>({
      nzContent: SettingsComponent,
      // One button where ng-zorro would put two, driven by the panel itself: hidden outright where the service is down, nothing being savable then.
      nzFooter: [{
        disabled: panel => !panel?.chosen(),
        label: 'Enregistrer',
        onClick: panel => panel?.submit(),
        show: panel => !panel?.unreachable(),
        type: 'primary',
      }],
      nzTitle: 'Paramétrage',
    });
    modal.componentInstance?.load().catch(() => {}); // the panel shows its own unreachable notice
  };

  // A first run, or a world just wiped: the panel opens by itself. Read off the asset, the service being needed for none of it — a deleted file reads as empty.
  private _openSettingsIfUnset(): void {
    this._http.get<Settings>(SETTINGS_FILE).pipe(catchError(() => of<Settings>({}))).subscribe((recorded) => {
      if (!recorded.savePath) this.openSettings();
    });
  }

  // The browser cannot reach the filesystem: `scripts/watch-saves.mjs` does the erasing, and it only runs under `yarn start`.
  private async _wipe(): Promise<void> {
    try {
      const answer = await fetch(RESET_ENDPOINT, { method: 'POST' });
      if (!answer.ok) throw new Error(String(answer.status));
      globalThis.location.assign('/'); // back to the chronicler's own page, not the chapter that has just ceased to exist
    } catch {
      this._modal.error({
        nzContent: `Le service local n'a pas répondu sur ${RESET_ENDPOINT}. Il tourne avec \`yarn start\` — un \`ng serve\` seul ne l'expose pas.`,
        nzTitle: 'Suppression impossible',
      });
    }
  }

}

import { Component, inject } from '@angular/core';

import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { RESET_ENDPOINT } from '../../../constants';
import { ChroniclerService } from '../../../services';

@Component({
  selector: 'app-sider-actions',
  imports: [NzButtonModule, NzModalModule, NzTooltipModule],
  templateUrl: './sider-actions.component.html',
  styleUrl: './sider-actions.component.scss',
})
export class SiderActionsComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _modal = inject(NzModalService);

  protected chapters = this._chronicler.chapters;

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

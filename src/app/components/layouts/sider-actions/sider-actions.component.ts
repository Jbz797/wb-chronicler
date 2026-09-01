import { Component, inject } from '@angular/core';

import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzModalModule, NzModalService } from 'ng-zorro-antd/modal';
import { NzTooltipModule } from 'ng-zorro-antd/tooltip';

import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { BOOT_SETTINGS, RESET_ENDPOINT } from '../../../constants';
import { ChroniclerService } from '../../../services';
import { SettingsComponent } from '../settings/settings.component';

@Component({
  selector: 'app-sider-actions',
  imports: [NzButtonModule, NzModalModule, NzTooltipModule, TranslatePipe],
  templateUrl: './sider-actions.component.html',
  styleUrl: './sider-actions.component.scss',
})
export class SiderActionsComponent {

  private readonly _chronicler = inject(ChroniclerService);
  private readonly _modal = inject(NzModalService);
  private readonly _translate = inject(TranslateService);

  protected chapters = this._chronicler.chapters;

  constructor() {
    this._openSettingsIfUnset();
  }

  // Nothing is undone from here, so the count is spelled out and the confirm button says what it does rather than "OK".
  protected confirmNewGame = (): void => {
    const count = this.chapters().length;
    this._modal.confirm({
      nzCancelText: this._translate.instant('ui_cancel') as string,
      nzContent: this._translate.instant('ui_wipe_warning', { count }) as string,
      nzOkDanger: true,
      nzOkText: this._translate.instant('ui_wipe_all') as string,
      nzOnOk: () => this._wipe(),
      nzTitle: this._translate.instant('ui_start_over') as string,
    });
  };

  // Opened from the button, and on its own at startup while no save is on record — without one the chronicler has nothing to read.
  protected openSettings = (): void => {
    const modal = this._modal.create<SettingsComponent>({
      nzContent: SettingsComponent,
      // One button where ng-zorro would put two, driven by the panel itself: hidden outright where the service is down, nothing being savable then.
      nzFooter: [{
        disabled: panel => !panel?.chosen() || !panel.hasLang(), // no tongue, no save: the chronicler would have none to write its chapters in
        label: this._translate.instant('ui_save') as string,
        onClick: panel => panel?.submit(),
        show: panel => !panel?.unreachable(),
        type: 'primary',
      }],
      nzTitle: this._translate.instant('ui_settings') as string,
    });
    modal.componentInstance?.load().catch(() => {}); // the panel shows its own unreachable notice
  };

  // A first run, or a world just wiped: the panel opens by itself. Off what the startup already read — a deleted file reads as empty, which is the case to catch.
  private _openSettingsIfUnset(): void {
    if (!inject(BOOT_SETTINGS).savePath) this.openSettings();
  }

  // The browser cannot reach the filesystem: `scripts/watch-saves.mjs` does the erasing, and it only runs under `yarn start`.
  private async _wipe(): Promise<void> {
    try {
      const answer = await fetch(RESET_ENDPOINT, { method: 'POST' });
      if (!answer.ok) throw new Error(String(answer.status));
      globalThis.location.assign('/'); // back to the chronicler's own page, not the chapter that has just ceased to exist
    } catch {
      this._modal.error({
        nzContent: this._translate.instant('ui_service_silent', { endpoint: RESET_ENDPOINT }) as string,
        nzTitle: this._translate.instant('ui_wipe_impossible') as string,
      });
    }
  }

}

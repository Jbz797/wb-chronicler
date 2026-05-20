import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { NzLayoutModule } from 'ng-zorro-antd/layout';

import { ChapterOverviewComponent, MapPreviewComponent, NavComponent } from './components/layouts';
import { GithubStarsComponent } from './components/misc';
import { ChroniclerService } from './services/chronicler.service';

@Component({
  selector: 'app-root',
  imports: [ChapterOverviewComponent, GithubStarsComponent, MapPreviewComponent, NavComponent, NzLayoutModule, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {

  protected chapters = inject(ChroniclerService).chapters;

}

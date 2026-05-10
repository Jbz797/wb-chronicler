import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { NzMenuModule } from 'ng-zorro-antd/menu';

import { PAGES } from '../constants';
import { ChroniclerService } from '../services/chronicler.service';

@Component({
  selector: 'app-nav',
  imports: [NzMenuModule, RouterLink],
  templateUrl: './nav.html',
  styleUrl: './nav.scss',
})
export class NavComponent {

  protected chapters = inject(ChroniclerService).chapters;
  protected pages = PAGES;

}

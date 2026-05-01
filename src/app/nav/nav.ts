import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { NzMenuModule } from 'ng-zorro-antd/menu';

import { PAGES } from '../constants';

@Component({
  selector: 'app-nav',
  imports: [NzMenuModule, RouterLink, RouterLinkActive],
  templateUrl: './nav.html',
  styleUrl: './nav.scss',
})
export class NavComponent {

  protected readonly items = PAGES;

}

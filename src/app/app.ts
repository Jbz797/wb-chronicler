import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { NzLayoutModule } from 'ng-zorro-antd/layout';

import { NavComponent } from './nav/nav';

@Component({
  selector: 'app-root',
  imports: [NavComponent, NzLayoutModule, RouterOutlet],
  templateUrl: './app.html',
})
export class App {}

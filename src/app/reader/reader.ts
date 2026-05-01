import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';

import { MarkdownComponent } from 'ngx-markdown';
import { map } from 'rxjs';

import { findPage } from '../constants';

@Component({
  selector: 'app-reader',
  imports: [MarkdownComponent],
  templateUrl: './reader.html',
  styleUrl: './reader.scss',
})
export class ReaderComponent {

  private readonly _slug = toSignal(inject(ActivatedRoute).paramMap.pipe(map(p => p.get('slug'))), { requireSync: true });
  protected readonly src = computed(() => findPage(this._slug()).src);

}

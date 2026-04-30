import { Component, input } from '@angular/core';

import { MarkdownComponent } from 'ngx-markdown';

@Component({
  selector: 'app-reader',
  imports: [MarkdownComponent],
  templateUrl: './reader.html',
  styleUrl: './reader.scss',
})
export class ReaderComponent {

  public readonly src = input.required<string>();

}

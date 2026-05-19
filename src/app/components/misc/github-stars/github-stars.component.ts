import { HttpClient } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

import { catchError, map, of } from 'rxjs';

@Component({
  selector: 'app-github-stars',
  templateUrl: './github-stars.component.html',
  styleUrl: './github-stars.component.scss',
})
export class GithubStarsComponent {

  protected readonly stars = toSignal(
    inject(HttpClient).get<{ stargazers_count: number }>('https://api.github.com/repos/Jbz797/wb-chronicler').pipe(
      map(r => r.stargazers_count),
      catchError(() => of(null)),
    ),
    { initialValue: null },
  );

}

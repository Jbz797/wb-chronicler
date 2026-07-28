import { Component, effect, ElementRef, input, viewChild } from '@angular/core';

import { ActorSpriteHelpers } from '../../../helpers';
import { PersonInfo } from '../../../interfaces';

@Component({
  selector: 'app-actor-portrait',
  template: '<canvas #canvas class="portrait"></canvas>',
  styles: 'canvas { display: block }', // off the baseline — inline, its descender gap lifted the wrapped portrait 2.3px above the bare prose one.
})
export class ActorPortraitComponent {

  public readonly actor = input.required<PersonInfo>(); // registry entry — species, sex, head, phenotype, realm and wielded weapon

  private readonly _canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');

  constructor() {
    effect(() => ActorSpriteHelpers.paint(this._canvas().nativeElement, this.actor()).catch(() => {})); // a missing sheet leaves the canvas collapsed
  }

}

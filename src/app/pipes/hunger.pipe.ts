import { Pipe, PipeTransform } from '@angular/core';

// `.tier-*` styles live in `src/styles.scss`.
@Pipe({ name: 'hunger', standalone: true })
export class HungerPipe implements PipeTransform {

  // Anchored on WB hunger, not happiness: `Actor.isHungry` answers at half the cap or under (`nutrition_level_hungry`), and only an empty belly starves.
  public transform(nutrition: number, max: number): string {
    if (nutrition <= 0) return 'tier-low';
    return nutrition > max * 0.5 ? 'tier-full' : 'tier-mid';
  }

}

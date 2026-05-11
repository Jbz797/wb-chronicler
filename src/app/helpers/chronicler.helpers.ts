export class ChroniclerHelpers {

  public static yearFromWorldTime = (worldTime: number): number => Math.floor(worldTime / 60) + 1;

}

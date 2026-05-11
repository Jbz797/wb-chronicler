// Color applied to intelligent species text in the reader (cf. chronicler.md).
// Hues derived from the dominant non-neutral pixel of each species icon in `src/assets/img/species/` (icons fetched from the WorldBox wiki).
// Non-intelligent species are intentionally absent — they get the icon but no text color.
export const SPECIES_COLORS: Readonly<Record<string, string>> = {
  alien: '#28af28',
  angle: '#617561',
  bandit: '#505050',
  cold_one: '#429595',
  demon: '#701020',
  druid: '#704020',
  dwarf: '#a56331',
  elf: '#008020',
  evil_mage: '#ba2b1d',
  ghost: '#617561',
  human: '#4d6b8a',
  necromancer: '#802080',
  orc: '#204030',
  plague_doctor: '#303030',
  snowman: '#5c7b7b',
  white_mage: '#409696',
};

// Color applied to intelligent species text in the reader (cf. chronicler.md).
// Hues derived from the dominant non-neutral pixel of each species icon in `src/assets/img/species/` (icons fetched from the WorldBox wiki).
// Non-intelligent species are intentionally absent — they get the icon but no text color.
export const SPECIES_COLORS: Readonly<Record<string, string>> = {
  alien: '#5fc94a',
  angle: '#f5c63a',
  bandit: '#c14040',
  cold_one: '#7ac8e3',
  demon: '#d33a2a',
  druid: '#7a9b3a',
  dwarf: '#a56331',
  elf: '#8fd35a',
  evil_mage: '#a83a6a',
  ghost: '#7a8a9c',
  human: '#d9a86c',
  necromancer: '#5a3a8e',
  orc: '#5a8a3a',
  plague_doctor: '#2c3a4a',
  snowman: '#5a90b8',
  white_mage: '#c9a04a',
};

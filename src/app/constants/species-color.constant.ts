// Color applied to intelligent species text in the reader (cf. chronicler.md).
// human/elf/dwarf/orc: darkest hue across their canonical `preferred_colors` palettes (source: WB `initCivsClassic` IL + `colors_general` TextAsset).
// Other intelligent species: handpicked dominant-icon hue. Non-intelligent species: intentionally absent (icon shown, no text color).
export const SPECIES_COLORS: Readonly<Record<string, string>> = {
  alien: '#5fc94a',
  angle: '#f5c63a',
  bandit: '#c14040',
  cold_one: '#7ac8e3',
  demon: '#d33a2a',
  druid: '#7a9b3a',
  dwarf: '#9A6324', // preferred yellow/orange/brown
  elf: '#3CB44B', // preferred green/lime/lavender
  evil_mage: '#a83a6a',
  ghost: '#7a8a9c',
  human: '#00675C', // preferred blue/navy/teal/cyan
  necromancer: '#5a3a8e',
  orc: '#262626', // preferred red/orange/brown/maroon/black
  plague_doctor: '#2c3a4a',
  snowman: '#5a90b8',
  white_mage: '#c9a04a',
};

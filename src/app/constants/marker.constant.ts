// Single-letter prefixes for the marked inline extensions (`[k id Nom]`): a letter already taken sends the marker to another of the word's own — cLan, allIance.
export const INLINE_MARKER = {
  Alliance: 'i',
  Boat: 'o',
  Book: 'b',
  City: 'c',
  Clan: 'l',
  Culture: 't',
  Family: 'f',
  Kingdom: 'k',
  Language: 'a',
  Person: 'p',
  Religion: 'e',
  Resource: 'r',
  Species: 's',
  Subspecies: 'u',
  War: 'w',
} as const;

// Text hue for an intelligent species in the reader (cf. chronicler.md): human/elf/dwarf/orc take the darkest of their canonical `preferred_colors` palettes,
// off WB's `initCivsClassic` IL and its `colors_general` TextAsset. The others take their icon's dominant hue, handpicked; the unintelligent ones none at all.
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

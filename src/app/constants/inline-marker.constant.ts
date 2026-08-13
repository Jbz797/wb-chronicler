// Single-letter prefixes used in the marked inline extensions: `[k id Nom]`, `[p id Nom]`, etc.
export const INLINE_MARKER = {
  City: 'c',
  Clan: 'l', // `c` is the city's and `k` the kingdom's, so a clan takes the second letter of its own name
  Family: 'f',
  Kingdom: 'k',
  Person: 'p',
  Resource: 'r',
  Species: 's',
  Subspecies: 'u', // `s` is the species', so a subspecies takes the letter of its own prefix — sUbspecies, as a cLan took its second
} as const;

// Single-letter prefixes used in the marked inline extensions: `[k id Nom]`, `[p id Nom]`, etc.
export const INLINE_MARKER = {
  Book: 'b',
  City: 'c',
  Clan: 'l', // `c` is the city's and `k` the kingdom's, so a clan takes the second letter of its own name
  Culture: 't', // `c`, `u` and `l` are all spoken for, so a culture takes the next letter of its own name — culTure
  Family: 'f',
  Kingdom: 'k',
  Language: 'a', // `l` is the clan's, so a language takes its second letter — lAnguage, as a cLan took its own
  Person: 'p',
  Religion: 'e', // `r` is the resource's, so a religion takes its second letter — rEligion, as a cLan and a lAnguage took theirs
  Resource: 'r',
  Species: 's',
  Subspecies: 'u', // `s` is the species', so a subspecies takes the letter of its own prefix — sUbspecies, as a cLan took its second
} as const;

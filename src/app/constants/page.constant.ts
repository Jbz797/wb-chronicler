export interface Page { label: string; slug: string; src: string }

export const PAGES: readonly Page[] = [
  { label: 'Chronicler', slug: 'chronicler', src: 'assets/world/chronicler.md' },
  { label: 'Tags', slug: 'tags', src: 'assets/world/history/tags.md' },
];

// Resolve a slug to its corresponding Page, fallback to the first one
export function findPage(slug: string | null): Page {
  return PAGES.find(p => p.slug === slug) ?? PAGES[0]!;
}

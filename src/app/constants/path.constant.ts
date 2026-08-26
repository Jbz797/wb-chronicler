import { Page } from '../interfaces';

export const WORLD_DIR = 'assets/world';

export const HISTORY_DIR = `${WORLD_DIR}/history`;
export const RESET_ENDPOINT = 'http://127.0.0.1:4223/reset'; // `watch-saves.mjs` answers here; the browser cannot erase a world, and it needs `yarn start`.
export const SAVES_DIR = `${WORLD_DIR}/saves`;

export const PAGES: Page[] = [
  { label: 'Chronicler', mdUrl: `${WORLD_DIR}/chronicler.md`, slug: 'chronicler' },
  { label: 'Tags', mdUrl: `${HISTORY_DIR}/tags.md`, slug: 'tags' },
  { label: 'Tools', mdUrl: `${WORLD_DIR}/tools/tools.md`, slug: 'tools' },
];

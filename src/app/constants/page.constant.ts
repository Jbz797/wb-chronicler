import { Page } from '../interfaces';

import { HISTORY_DIR, WORLD_DIR } from './path.constant';

export const PAGES: Page[] = [
  { label: 'Chronicler', mdUrl: `${WORLD_DIR}/chronicler.md`, slug: 'chronicler' },
  { label: 'Tags', mdUrl: `${HISTORY_DIR}/tags.md`, slug: 'tags' },
];

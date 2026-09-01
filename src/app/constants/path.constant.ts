import { InjectionToken } from '@angular/core';

import { Page, Settings } from '../interfaces';

export const WORLD_DIR = 'assets/world';

export const BOOT_SETTINGS = new InjectionToken<Settings>('boot settings'); // `settings.json` at boot, read once: the nav wants the mode on first paint.
export const HISTORY_DIR = `${WORLD_DIR}/history`;
export const SAVES_DIR = `${WORLD_DIR}/saves`;
export const CHAPTER_INDEX = `${SAVES_DIR}/index.json`; // every chapter in one file, so the nav names them all without opening a single one
export const SERVICE_URL = 'http://127.0.0.1:4223'; // `scripts/watch-saves.mjs`, reaching the disk the browser cannot — and only under `yarn start`.
export const SETTINGS_FILE = `${HISTORY_DIR}/settings.json`; // an asset, so what it records is read without the service — which alone can write it

export const RESET_ENDPOINT = `${SERVICE_URL}/reset`;
export const SAVES_ENDPOINT = `${SERVICE_URL}/saves`;
export const SETTINGS_ENDPOINT = `${SERVICE_URL}/settings`;

// The workshop's pages, and its alone: outside dev mode the nav lists none and the reader resolves none, so a stale link renders blank, not the manual.
export const PAGES: Page[] = [
  { label: 'Chronicler', mdUrl: `${WORLD_DIR}/chronicler.md`, slug: 'chronicler' },
  { label: 'Tags', mdUrl: `${WORLD_DIR}/tags.md`, slug: 'tags' },
  { label: 'Tools', mdUrl: `${WORLD_DIR}/tools/tools.md`, slug: 'tools' },
];

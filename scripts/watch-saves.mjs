// Watches src/assets/world/saves/ and touches src/main.ts to force ng serve to rebuild
// and re-glob assets when a new chapter file or folder appears — ng serve does not pick up
// newly-added asset files on its own. Modifications of existing files are left to ng serve.
// A burst of additions (a whole chapter folder) is debounced into a single touch.

import { watch } from 'chokidar';
import { utimes } from 'node:fs/promises';

const DEBOUNCE_MS = 1000;
const TRIGGER = 'src/main.ts';
const WATCH = 'src/assets/world/saves';

let timer;

// Coalesce a burst of additions into one main.ts touch.
const scheduleTouch = () => {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const now = new Date();
    await utimes(TRIGGER, now, now);
    console.log('[watch] new file/folder in saves — triggered rebuild');
  }, DEBOUNCE_MS);
};

watch(WATCH, { ignoreInitial: true }).on('add', scheduleTouch).on('addDir', scheduleTouch);

console.log(`[watch] watching ${WATCH} for new chapters`);

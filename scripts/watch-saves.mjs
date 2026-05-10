// Watches src/assets/world/saves/ for new files and folders and touches src/main.ts
// to force ng serve to rebuild and re-glob assets. ng serve handles modifications of
// existing files on its own — we only fire on `addDir` to avoid double rebuilds.

import { watch } from 'chokidar';
import { utimes } from 'node:fs/promises';

const TRIGGER = 'src/main.ts';
const WATCH = 'src/assets/world/saves';

const touchTrigger = async () => {
  const now = new Date();
  await utimes(TRIGGER, now, now);
};

watch(WATCH, { ignoreInitial: true }).on('addDir', touchTrigger);

console.log(`[watch] watching ${WATCH} for new chapters`);

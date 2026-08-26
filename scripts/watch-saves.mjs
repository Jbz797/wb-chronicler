// Two services `ng serve` cannot provide on its own, both local to development:
//  · watches src/assets/world/saves/ and touches src/main.ts so a newly-added chapter file or folder is re-globbed (edits of existing files it handles itself);
//  · answers the reader's "new game" button, which needs a hand on the filesystem the browser will never have.

import { watch } from 'chokidar';
import { readdir, rm, utimes } from 'node:fs/promises';
import { createServer } from 'node:http';

const DEBOUNCE_MS = 1000;
const HISTORY = 'src/assets/world/history';
const PORT = 4223; // `sider-actions.component.ts` calls this one
const SAVES = 'src/assets/world/saves';
const TRIGGER = 'src/main.ts';

// What a world is made of, beside its chapters. `tags.md` and `chronicler.md` stay: they are the chronicler's instructions, not the world he wrote.
const WORLD_FILES = [`${HISTORY}/map_stats.s3db`, `${HISTORY}/places.json`, `${HISTORY}/world.json`];

const pending = { touch: undefined };

// Coalesce a burst of additions into one main.ts touch.
const scheduleTouch = () => {
  clearTimeout(pending.touch);
  pending.touch = setTimeout(async () => {
    const now = new Date();
    await utimes(TRIGGER, now, now);
    console.log('[watch] new file/folder in saves — triggered rebuild');
  }, DEBOUNCE_MS);
};

// Empties `saves/` rather than removing it — the folder is declared in angular.json, and `chapter/new.py` writes straight into it.
const wipeWorld = async () => {
  let chapters = [];
  try {
    chapters = await readdir(SAVES);
  } catch {
    chapters = []; // the folder is gone or was never made: nothing to wipe there, though the world files below may still stand
  }
  await Promise.all(chapters.map((entry) => rm(`${SAVES}/${entry}`, { force: true, recursive: true })));
  await Promise.all(WORLD_FILES.map((file) => rm(file, { force: true })));
  return chapters.length;
};

watch(SAVES, { ignoreInitial: true }).on('add', scheduleTouch).on('addDir', scheduleTouch);

createServer(async (request, response) => {
  // Loopback only, and the caller must be a page served from this machine: the endpoint erases a world, so no other origin gets to ask.
  const origin = request.headers.origin ?? '';
  if (!/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    response.writeHead(403).end();
    return;
  }

  response.setHeader('Access-Control-Allow-Origin', origin);
  response.setHeader('Access-Control-Allow-Methods', 'OPTIONS, POST');
  if (request.method === 'OPTIONS') {
    response.writeHead(204).end();
    return;
  }
  if (request.method !== 'POST' || request.url !== '/reset') {
    response.writeHead(404).end();
    return;
  }

  try {
    const wiped = await wipeWorld();
    console.log(`[reset] world wiped — ${wiped} chapters removed`);
    response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({ chapters: wiped }));
  } catch (error) {
    console.error('[reset] failed', error);
    response.writeHead(500, { 'content-type': 'application/json' }).end(JSON.stringify({ error: String(error) }));
  }
}).listen(PORT, '127.0.0.1');

console.log(`[watch] watching ${SAVES} for new chapters · reset endpoint on 127.0.0.1:${PORT}`);

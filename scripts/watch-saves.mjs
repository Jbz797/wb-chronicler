// Three services `ng serve` cannot provide on its own, all local to development:
//  · watches src/assets/world/saves/ and touches src/main.ts so a newly-added chapter file or folder is re-globbed (edits of existing files it handles itself);
//  · answers the reader's "new game" button, which needs a hand on the filesystem the browser will never have;
//  · finds and records where WorldBox keeps its live save — the one path the whole toolchain hangs on, and the only thing that ever tied it to one OS.

import { watch } from 'chokidar';
import {
  readdir, readFile, rm, stat, utimes, writeFile,
} from 'node:fs/promises';
import { createServer } from 'node:http';
import { homedir } from 'node:os';
import path from 'node:path';
import { json } from 'node:stream/consumers';

const PORT = 4223; // `path.constant.ts` holds the reader's side of this
const PROTON_SUFFIX = 'steamapps/compatdata/1206560/pfx/drive_c/users/steamuser/AppData/LocalLow/mkarpenko/WorldBox/saves';
const SAVES = 'src/assets/world/saves';

// Per platform, where Unity lays them down, each read from the player's home; under Proton the Windows layout sits in the prefix, in either Steam library.
const SAVE_ROOTS = {
  darwin: ['Library/Application Support/mkarpenko/WorldBox/saves'],
  linux: ['.config/unity3d/mkarpenko/WorldBox/saves', `.steam/steam/${PROTON_SUFFIX}`, `.local/share/Steam/${PROTON_SUFFIX}`],
  win32: ['AppData/LocalLow/mkarpenko/WorldBox/saves'],
};

// A folder the game never wrote to is no error here — that machine simply keeps nothing there. Serves the save roots and `saves/` alike.
const entriesIn = async (base) => {
  try {
    return await readdir(base);
  } catch {
    return [];
  }
};

// Never written, or left half-written: both come back as an empty object for the caller to read through.
const readJson = async (file) => {
  try {
    return JSON.parse(await readFile(file, 'utf8'));
  } catch {
    return {};
  }
};

// The reader's own side, on loopback and from a page served here: these routes erase a world and repoint the toolchain, so no other origin gets to ask.
class LocalService {
  #routes;

  constructor(scout, store) {
    this.#routes = {
      'GET /saves': () => scout.list(),
      'POST /reset': async () => ({ chapters: await store.wipe() }),
      'POST /settings': async (body) => {
        await store.record(body.lang, body.savePath);
        return { lang: body.lang, savePath: body.savePath };
      },
    };
  }

  // Only `POST /settings` carries one, and parsing an empty stream throws — so a body is read where one is expected and nowhere else.
  static async #body(request) {
    if (request.method !== 'POST') return {};
    try {
      return await json(request);
    } catch {
      return {};
    }
  }

  listen(port) {
    createServer((request, response) => this.#handle(request, response)).listen(port, '127.0.0.1');
  }

  // Answers in JSON whatever happens, the reader having no other way to tell a refused path from a service that never came up.
  async #handle(request, response) {
    const origin = request.headers.origin ?? '';
    if (!/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
      response.writeHead(403).end();
      return;
    }

    response.setHeader('Access-Control-Allow-Origin', origin);
    response.setHeader('Access-Control-Allow-Headers', 'content-type');
    response.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS, POST');
    if (request.method === 'OPTIONS') {
      response.writeHead(204).end();
      return;
    }

    const route = this.#routes[`${request.method} ${request.url}`];
    if (!route) {
      response.writeHead(404).end();
      return;
    }

    try {
      const answer = JSON.stringify(await route(await LocalService.#body(request)));
      console.log(`[${request.method} ${request.url}]`, answer.slice(0, 120));
      response.writeHead(200, { 'content-type': 'application/json' }).end(answer);
    } catch (error) {
      console.error(`[${request.method} ${request.url}] failed`, error);
      response.writeHead(500, { 'content-type': 'application/json' }).end(JSON.stringify({ error: String(error) }));
    }
  }
}

// chokidar fires once per file, and a new chapter folder lands as a dozen of them — one rebuild answers them all.
class RebuildTrigger {
  #debounceMs = 1000;
  #timer;
  #trigger = 'src/main.ts';

  start() {
    watch(SAVES, { ignoreInitial: true }).on('add', () => this.#schedule()).on('addDir', () => this.#schedule());
  }

  #schedule() {
    clearTimeout(this.#timer);
    this.#timer = setTimeout(async () => {
      const now = new Date();
      await utimes(this.#trigger, now, now);
      console.log('[watch] new file/folder in saves — triggered rebuild');
    }, this.#debounceMs);
  }
}

// What WorldBox itself left on this machine: every slot it has written, and the world each one holds.
class SaveScout {
  #meta = 'map.meta';
  #roots = SAVE_ROOTS[process.platform] ?? [];
  #save = 'map.wbox';

  // Every save slot, newest first: the one written last is the one they mean. Walked in parallel — an absent Proton prefix costs no wait.
  async list() {
    const slots = await Promise.all(this.#roots.map((root) => this.#slotsIn(root)));
    const saves = await Promise.all(slots.flat().map((savePath) => this.#describe(savePath)));
    return saves.flat().toSorted((a, b) => b.mtime - a.mtime);
  }

  // A slot folder holding no save is passed over rather than reported — the empty list drops out of the `flat()` that gathers them.
  async #describe(savePath) {
    try {
      const [{ mtimeMs, size }, world] = await Promise.all([stat(savePath), this.#worldName(savePath)]);
      return [{
        mtime: Math.round(mtimeMs), path: savePath, size, world,
      }];
    } catch {
      return [];
    }
  }

  // Where a save would sit in each of a root's slot folders, whether or not the game ever wrote one there.
  async #slotsIn(root) {
    const base = path.join(homedir(), root);
    const entries = await entriesIn(base);
    return entries.map((slot) => path.join(base, slot, this.#save));
  }

  // WorldBox lays the world's own name beside the save, in plain JSON: a slot is then picked by the world it holds rather than by its number.
  async #worldName(savePath) {
    const meta = await readJson(path.join(path.dirname(savePath), this.#meta));
    return meta.mapStats?.name;
  }
}

// The chronicle's own files: the chapters a world leaves behind, and the setting naming the save they grow from — the reader reads that off the assets, not here.
class WorldStore {
  #history = 'src/assets/world/history';
  #settings = `${this.#history}/settings.json`;

  // Refuses a path that leads nowhere: the whole toolchain reads through this one setting, and a wrong one only fails much later, inside `shared.py`.
  // `lang` rides along: it is the tongue the chronicler writes its chapters in, which the reader's own panels merely follow.
  async record(lang, savePath) {
    await stat(savePath);
    await writeFile(this.#settings, `${JSON.stringify({ lang, savePath }, undefined, 2)}\n`);
  }

  // Empties `saves/` rather than removing it — angular.json declares it, `new.py` writes into it — then all of `history/`; what outlives a world sits elsewhere.
  async wipe() {
    const chapters = await entriesIn(SAVES);
    const history = [`${this.#history}/map_stats.s3db`, `${this.#history}/places.json`, `${this.#history}/world.json`, this.#settings];
    const doomed = [...chapters.map((entry) => `${SAVES}/${entry}`), ...history];
    await Promise.all(doomed.map((entry) => rm(entry, { force: true, recursive: true })));
    return chapters.length;
  }
}

const rebuilds = new RebuildTrigger();
const service = new LocalService(new SaveScout(), new WorldStore());

rebuilds.start();
service.listen(PORT);

console.log(`[watch] watching ${SAVES} · service on 127.0.0.1:${PORT} (${process.platform})`);

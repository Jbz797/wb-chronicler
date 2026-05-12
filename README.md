<p align="center">
  <img src="src/assets/img/favicon.svg" alt="WB Chronicler Logo" width="120" height="120">
</p>

<h1 align="center">WB Chronicler</h1>

<p align="center">Tolkien-style chronicle for <strong>WorldBox</strong> playthroughs</p>

<p align="center">
    <a href="https://github.com/Jbz797/wb-chronicler/blob/master/LICENSE"><img src="https://img.shields.io/github/license/Jbz797/wb-chronicler" alt="License" /></a>
    <img src="https://img.shields.io/badge/Angular-21-DD0031?logo=angular&logoColor=white" alt="Angular 21" />
    <img src="https://img.shields.io/badge/Claude%20Code-required-D97757?logo=anthropic&logoColor=white" alt="Claude Code required" />
</p>

<br>

## Overview

Claude Code turns your **WorldBox** save files into narrative chapters, rendered in a parchment-themed Angular reader. The player runs the game in pure observation mode, the chronicler writes the story.

## How it works

The player runs **WorldBox** in pure observation mode (zero intervention, sandbox laws). When a save is ready:

1. **The Chronicler** — Claude Code, launched from `src/assets/world/`, reads the rules in `chronicler.md`, decodes the WorldBox save (`map.wbox` zlib-compressed JSON, plus the `map_stats.s3db` SQLite), and writes the next narrative chapter in a Tolkien-inspired voice (French, no pastiche, every claim traced back to data).

2. **The Reader** — an Angular SPA with NG-ZORRO and ngx-markdown displays the chapters and the rules document on a parchment-themed reader, with a left side nav for navigation and a right pane reserved for future content.

Each chapter is a self-contained folder under `saves/C<n>/` carrying its own narrative, metadata, the original save snapshot, and the map preview at that moment in time.

> **Notes**
> - **One save = one chapter.** The system is built around **manual saves only** — disable WorldBox auto-saves before you start. Each time the player triggers a save, the chronicler picks it up and writes the next chapter.
> - **Claude Max** (or higher) is recommended — the chronicler reads, cross-checks, and writes a multi-section chapter on every save.
> - Narrative output is **French only** for now.
> - **macOS only.** The live WorldBox save path used by `chronicler.md` and the `tools/` scripts is hardcoded for macOS (`$HOME/Library/Application Support/mkarpenko/WorldBox/saves/save1/`). On other OSes, update those references to match the local path.

## Chronicle layout

The chronicle lives under [src/assets/world/](src/assets/world/) — full structure and conventions are documented in `chronicler.md`:

```
src/assets/world/
├── chronicler.md
├── history/
├── saves/
└── tools/
```

The contents of `history/` and `saves/` are gitignored — every player's chronicle stays local to their machine.

## Dev

Requires **Node 22+** and **Yarn 4** (Corepack-managed, see `packageManager` in `package.json`).

```sh
yarn install
yarn start          # ng serve on http://localhost:4200
yarn build          # production build
yarn lint           # ESLint + stylelint + prettier --check
yarn lint:fix       # auto-fix all three
```

## Tech stack

- **Angular 21** (standalone components, signals, zoneful)
- **NG-ZORRO 21** (dark layout, custom gold/parchment palette)
- **ngx-markdown 21** + Marked + Prism.js (gruvbox-dark)
- **LESS** for ng-zorro theme overrides (mirrors `src/variables.scss`)
- **TypeScript 5.9**, ESLint, Stylelint, Prettier

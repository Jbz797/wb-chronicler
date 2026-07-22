<p align="center">
  <img src="src/assets/img/favicon.svg" alt="WB Chronicler Logo" width="120" height="120">
</p>

<h1 align="center">WB Chronicler</h1>

<p align="center">Tolkien-style chronicle for <strong>WorldBox</strong> playthroughs</p>

<p align="center">
    <a href="https://github.com/Jbz797/wb-chronicler/blob/master/LICENSE"><img src="https://img.shields.io/github/license/Jbz797/wb-chronicler" alt="License" /></a>
    <img src="https://img.shields.io/badge/Angular-22-DD0031?logo=angular&logoColor=white" alt="Angular 22" />
    <img src="https://img.shields.io/badge/Claude%20Code-required-D97757?logo=anthropic&logoColor=white" alt="Claude Code required" />
</p>

<br>

## Overview

Claude Code turns your **WorldBox** save files into narrative chapters, rendered in a parchment-themed Angular reader. The player runs the game in pure observation mode, the chronicler writes the story.

## How it works

The player runs **WorldBox** in pure observation mode (zero intervention, sandbox laws). When a save is ready:

1. **The Chronicler** — Claude Code, launched from `src/assets/world/`, reads the rules in `chronicler.md`, decodes the WorldBox save (`map.wbox` zlib-compressed JSON, plus the `map_stats.s3db` SQLite), and writes the next narrative chapter in a Tolkien-inspired voice (French, no pastiche, every claim traced back to data).

2. **The Reader** — an Angular SPA with NG-ZORRO and ngx-markdown displays the chapters and the rules document on a parchment-themed reader, with a left side nav for navigation and a right pane surfacing each chapter's stats — the world, the favorite character, and its village and kingdom.

Each chapter is a self-contained folder under `saves/C<n>/` carrying its own narrative, metadata, the original save snapshot, and the map preview at that moment in time.

> **Notes**
> - **One save = one chapter.** The system is built around **manual saves only** — disable WorldBox auto-saves before you start. Each time the player triggers a save, the chronicler picks it up and writes the next chapter.
> - **Claude Max** (or higher) is recommended — the chronicler reads, cross-checks, and writes a multi-section chapter on every save.
> - Narrative output is **French only** for now.
> - **macOS only.** The live WorldBox save path used by `chronicler.md` and the `tools/` scripts is hardcoded for macOS (`$HOME/Library/Application Support/mkarpenko/WorldBox/saves/save1/`). On other OSes, update those references to match the local path.

## State lives on disk, not in context

The chronicle runs as a **single, continuous Claude Code conversation** rather than a fresh session per chapter. Every durable piece of state is persisted to disk — the `chronicler.md` manual, the self-contained per-chapter folders, and the deterministic `tools/` extractors (a save → JSON on demand, same input → same output). Nothing that matters lives in the context window.

The model's **1M-token context window** lets that single thread run a long way before compaction is even needed. And because the filesystem holds everything durable, **compaction costs nothing** when it does happen — the conversation can be summarized as aggressively as needed and the agent simply re-grounds itself from these files. That's what makes the single-thread approach viable: more practical, and it keeps the model sharper than cold-starting.

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

```sh
yarn install
yarn start          # ng serve on http://localhost:4200
yarn build          # production build
yarn lint           # ESLint + stylelint + prettier --check
yarn lint:fix       # auto-fix all three
```

## Tech stack

- **Angular** (standalone components, signals, zoneful)
- **NG-ZORRO** (dark layout, custom gold/parchment palette)
- **ngx-markdown** + Marked + Prism.js (gruvbox-dark)
- **LESS** for ng-zorro theme overrides (mirrors `src/variables.scss`)
- **TypeScript**, ESLint, Stylelint, Prettier

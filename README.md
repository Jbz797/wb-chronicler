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

1. **The Chronicler** — the Claude Code CLI, run from a terminal with `src/assets/world/` as its working directory, reads the rules in `chronicler.md`, questions the world through the `tools/` commands it is given — a script per subject (`world`, `actor`, `city`, `geography`…) that decodes the `map.wbox` save (zlib-compressed JSON) and answers in JSON — browses the `map_stats.s3db` SQLite itself, and writes the next narrative chapter in a Tolkien-inspired voice (French, no pastiche, every claim traced back to data).

2. **The Reader** — an Angular SPA with NG-ZORRO and ngx-markdown displays the chapters and the rules document on a parchment-themed reader, with a left side nav for navigation and a right pane surfacing each chapter's stats — the world's leaderboards, the favorite character, and every body it belongs to: village, kingdom, clan, lineage…

Each chapter is a self-contained folder under `saves/C<n>/` carrying its own narrative, metadata, the original save snapshot, the map preview at that moment in time, and a registry per entity kind (`cities.json`, `persons.json`, `kingdoms.json`…) recording who was who.

> **Notes**
>
> - **One save = one chapter.** The system is built around **manual saves only** — disable WorldBox auto-saves before you start. The player decides when a chapter begins and asks for it; the chronicler then works from the latest save on disk, and an auto-save would slip in an intermediate state nobody chose. Overwriting the same WorldBox slot is safe: every chapter archives the save it was built from.
> - **Claude Max** (or higher) is recommended — the chronicler reads, cross-checks, and writes a multi-section chapter on every save.
> - Narrative output is **French only** for now.
> - **macOS, Windows and Linux.** On first run the reader opens its settings panel, finds the WorldBox saves this machine holds — including a Proton prefix on Linux — and records the one to follow.

## State lives on disk, not in context

The chronicle runs as a **single, continuous CLI session** — `claude` left open from one chapter to the next, rather than restarted for each. Every durable piece of state is persisted to disk — the `chronicler.md` manual, the self-contained per-chapter folders, and the deterministic `tools/` extractors (a save → JSON on demand, same input → same output). Nothing that matters lives in the context window.

The model's **1M-token context window** lets that single thread run a long way before compaction is even needed. And because the filesystem holds everything durable, **compaction costs nothing** when it does happen — the conversation can be summarized as aggressively as needed and the agent simply re-grounds itself from these files. That's what makes the single-thread approach viable: more practical, and it keeps the model sharper than cold-starting.

## Chronicle layout

The chronicle lives under [src/assets/world/](src/assets/world/) — full structure and conventions are documented in `chronicler.md`:

```
src/assets/world/
├── chronicler.md
├── tags.md
├── history/
├── saves/
└── tools/
```

Every player's chronicle stays local to their machine — the repo carries the tooling and the manual, not the story.

## Dev

```sh
cd src/assets/world && claude   # the chronicler: its working directory is the chronicle, and `chronicler.md` alone rules it
```

The CLI is what the chronicle expects — the session opens on a single order, _« Lis le chronicler.md »_, after which it reads and writes the files under `src/assets/world/` and runs the `tools/` scripts itself. The reader is a separate process:

```sh
yarn install
yarn start          # ng serve on http://localhost:4200, plus the local service the settings panel needs
yarn lint:fix       # auto-fix all three
```

## Tech stack

- **Angular** (standalone components, signals, zoneful)
- **NG-ZORRO** (dark layout, custom gold/parchment palette)
- **ngx-markdown** + Marked + Prism.js (gruvbox-dark)
- **LESS** for ng-zorro theme overrides (mirrors `src/variables.scss`)
- **TypeScript**, ESLint, Stylelint, Prettier

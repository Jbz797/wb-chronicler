# wb-chronicler

Tolkien-style chronicle for WorldBox playthroughs — Claude Code turns saves into narrative chapters, rendered in a parchment-themed Angular reader.

## How it works

The player runs **WorldBox** in pure observation mode (zero intervention, sandbox laws). When a save is ready:

1. **The Chronicler** — Claude Code, launched from `src/assets/world/`, reads the rules in `chronicler.md`, decodes the WorldBox save (`map.wbox` zlib-compressed JSON, plus the `map_stats.s3db` SQLite), and writes the next narrative chapter in a Tolkien-inspired voice (French, no pastiche, every claim traced back to data).

2. **The Reader** — an Angular SPA with NG-ZORRO and ngx-markdown displays the chapters and the rules document on a parchment-themed reader, with a left side nav for navigation and a right pane reserved for future content.

Each chapter is a self-contained folder under `saves/C<n>/` carrying its own narrative, metadata, the original save snapshot, and the map preview at that moment in time.

> **Notes**
> - **Claude Max** (or higher) is recommended — the chronicler reads, cross-checks, and writes a multi-section chapter on every save.
> - Narrative output is **French only** for now.

## Chronicle layout

The chronicle lives under [src/assets/world/](src/assets/world/):

```
.
├── chronicler.md       # Rules & conventions — single source of truth for the chronicler
├── history/
│   ├── tags.md         # Living vocabulary of event codes (NEW-FAVORITE, ALERT-*, etc.)
│   └── world.json      # World identity (name + description, set at C1)
├── saves/
│   ├── current.s3db    # Latest cumulative WorldBox SQLite (overwritten each save)
│   └── C<n>/           # One folder per chapter, numbered linearly
│       ├── chapter.json
│       ├── chapter.md
│       ├── map.wbox
│       └── preview.png
└── tools/              # Reusable Python scripts for save analysis
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

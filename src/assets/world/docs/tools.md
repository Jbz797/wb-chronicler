# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 28/10/26 22:38</p>

Chaque outil : `python tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON ou un `✗` seul sur stderr, qui refuse l'appel ou dit qu'il n'y a rien (`no … in this world` est une réponse, pas une panne), citée en abrégé : `kingdom … metadata`.

- **Un champ absent vaut rien** : un compte à 0, un drapeau faux, une liste ou un bloc vides se taisent, sauf où une glose dit le contraire ; absent, un compte vaut 0, ou 1 (`gen`, `level`, `past_chiefs`), `normal` (taxe).
- **Ce que fixe un filtre** (`-i`, un seul `-t`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre.
- **Les coordonnées** croissent vers l'est (x) et le nord (y), un `dir` aussi.
- **`sections`** : liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … laws`, `lineages`, `pairings` et `roster`, à nommer) ; un bloc nommé seul (section, `--to`, tuile) sort nu, plusieurs gardent leur clé.
- **Le suffixe `C<n>`** lit ce chapitre ; sans lui, le dernier ; l'outil `across` (`across C3-C7 actor 23 metadata --keep task`) pose la question à chacun, rangée par chapitre.
- **Une sortie se lit entière** : coupée (`head`), le JSON ne se lit plus ; les sections lourdes, une à une. Trop large, elle se résume (un compte par terre) : le détail se demande par ses filtres (`-i`, `-t`, une section).

| Commande          | Sections                                                                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `actor <id>`      | `companions`, `gear`, `inventory`, `kin`, `metadata`, `plot`, `ranks_in_species`, `stats`, `surroundings`, `traits`                    |
| `alliance <id>`   | `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `pop`, `ranks`, `wars`                                                     |
| `boat <id>`       | `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                        |
| `book <id>`       | `gains`, `metadata`, `origin`, `teaches`                                                                                               |
| `city <id>`       | `army`, `books`, `breakdown`, `buildings`, `gear`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `pop`, `ranks`, `rulers` |
| `clan <id>`       | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                               |
| `culture <id>`    | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `family <id>`     | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`                                                                         |
| `geography`       | `biomes`, `bodies`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `ridges`, `totals`, `waters`                  |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                          |
| `history`         | `dead_kingdoms`, `entity`, `log`, `world`                                                                                              |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `relations`, `rulers`, `wars`               |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `subspecies <id>` | `breakdown`, `leaders`, `metadata`, `pop`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                                           |
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `islet`, `rays`, `tile_info`                                                               |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                                   |
| `world`           | `boats`, `cumulative`, `laws`, `leaders`, `lineages`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`                            |

## Gloses :

`python tools/gloss/info.py <clé>` glose un champ en une ligne ; une balise **`gloss:<clé>`** y renvoie, comme `wiki:` au wiki. La clé suit la sortie, `<outil>.<section>.<champ>`, ou le champ seul s'il sert à plusieurs ; un fragment suffit (`pairings` rend la section entière). Avant de lire une section, `gloss <outil>.<section>` rend ses gloses, champs partagés compris, `gloss <outil>` tout l'outil ; plusieurs par virgules, chaque glose une fois.

## Options :

### `actor` :

- `--kills` : ses morts données, par chapitre (`gloss:actor.kills`)
- `--since C<n>` : ce qui a bougé depuis (`gloss:actor.since`, `gloss:to.then`)
- `--statuses` : ses statuts durables, par chapitre (`gloss:actor.statuses`)
- `--to <p<id> | x,y | b<id> | c<id> | i<terre> | lands | "<lieu>" | lake4 | burning | type>` : un corps, une tuile, un bâtiment, une cité (son centre), une terre, les terres qu'il peut gagner, un nom de `places.json` (`gloss:to.place`), une eau par son id, la flamme la plus proche, ou le plus proche de chaque type, famille, ressource, sol, gel (`frozen`) ou eau (`lake`, `water`…), `g:<sol>` un sol, même au nom d'un type, par virgules pour ceux-là seuls ; répété, chacun à part. `gloss:actor.to`.

### `geography` :

- `--since C<n>` : ce qui a bougé, en soldes (`gloss:geography.since`)
- `-i <id>` : une seule terre dans les sections rangées par terre, ou `islets` et `water` là où elles les comptent
- `-t <type>` : sous `positions`, types, familles (`trees`…) et ressources, par virgules, hors corps ; sous `biomes`, un biome ou un sol (`gloss:biomes`)
- `-w <eau>` : sous `waters`, une eau ou une famille (`lake`…)

### `history` :

- `entity <type> <id>` : les années d'une entité
- `log` : `--since C<n>` depuis un chapitre, `--actor <id>` celles d'un corps, `-t <event>` un type
- `world` : les comptes du monde à chaque fin d'année (`at_close`), un « jamais » dans le temps

### `tiles` :

- `-g <sol>` : un sol tel que `biomes` le nomme, `burning` ou `frozen` (`gloss:to_ground`)
- `-i <id>` : une terre par son id (`gloss:to_island`)
- `--to <x,y>` : cap et mesures, sous `to` si une section la rejoint ; à chaque bout, `--to` seul, un bâtiment `b<id>` (au plus proche), une cité `c<id>` (son centre), un corps `p<id>`, une eau `lake<id>` ou un `"<lieu>"` (`gloss:to.from`)
- `-w <eau>` : une eau, `lake<id>`, `river<id>` ou `sea<id>` (`gloss:to_body`)

### `world` :

- `laws` : les lois par leur libellé du jeu, celui de `wiki:World_Laws`
- `lineages` : chaque lignée vivante, `-t` celles d'une espèce. `gloss:lineages`.
- `pairings` : par espèce, la 1ʳᵉ naissance au plus tôt et son couple. `gloss:pairings`.
- `roster` : chaque vivant ; `-t` type ou famille, `--trait`, `--has`/`--lacks <compte>`, `--top <mesure>`, `--nearest <x,y | p<id>>` les plus proches à vol d'oiseau, `--with <champs>` jusqu'à 4, d'`actor … stats` ou d'une fiche, `--status`/`--task <id>`, `--stage <palier>`, `--sapient` ou `--beasts`, `--settle` (`settle` vrai ou `child`) et `--barred`, l'inverse, `-i` une terre, `islets` ou `water`, `--patch <x,y>` sa parcelle, `--<entité> <id>` (`--city`…) ses membres, `--since C<n>` ce qui a changé. `gloss:roster`.

---

## Carte :

`tools/map/show.py <x,y> [C<n>]` — cerne la tuile sur la carte du chapitre, rend le chemin de l'image. `--zoom <n>` : les n tuiles autour — **à lire toi-même** pour la forme d'une côte —, leurs parts en dessous, chaque sol nommé comme dans `biomes`, puis les tuiles en feu, la neige d'une roche, la glace et le gel.

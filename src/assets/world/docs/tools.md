# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 03/11/26 15:21</p>

Chaque outil : `python tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON ou un `✗` seul sur stderr, qui refuse l'appel ou dit qu'il n'y a rien (`no … in this world` est une réponse, pas une panne), citée en abrégé : `kingdom … metadata`.

- **Un champ absent vaut rien** : un compte à 0, un drapeau faux, une liste ou un bloc vides se taisent, sauf où une glose dit le contraire ; absent, un compte vaut 0, ou 1 (`gen`, `level`, `past_chiefs`), `normal` (taxe).
- **Ce que fixe un filtre** (`-i`, un seul `-t`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre.
- **Les coordonnées** croissent vers l'est (x) et le nord (y), un `dir` aussi.
- **`sections`** : liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … laws`, `lineages`, `pairings` et `roster`, à nommer) ; un bloc nommé seul (section, `--to`, tuile) sort nu, plusieurs gardent leur clé.
- **Le suffixe `C<n>`** lit ce chapitre ; sans lui, le dernier ; l'outil `across` pose la question à chacun, rangée par chapitre (`across C1-C9 world metadata --keep date` : la date de chacun).
- **Une sortie se lit entière** : coupée (`head`), le JSON ne se lit plus ; les sections lourdes, une à une. Trop large, elle se résume (un compte par terre) : le détail se demande par ses filtres (`-i`, `-t`, une section).

| Commande          | Sections                                                                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `actor <id>`      | `companions`, `gear`, `inventory`, `kin`, `metadata`, `plot`, `ranks_in_species`, `stats`, `surroundings`, `traits`, `victims`         |
| `alliance <id>`   | `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `pop`, `ranks`, `wars`                                                     |
| `boat <id>`       | `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                        |
| `book <id>`       | `gains`, `metadata`, `origin`, `teaches`                                                                                               |
| `city <id>`       | `army`, `books`, `breakdown`, `buildings`, `gear`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `pop`, `ranks`, `rulers` |
| `clan <id>`       | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                               |
| `culture <id>`    | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `family <id>`     | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`                                                                         |
| `geography`       | `biomes`, `bodies`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `ridges`, `totals`, `waters`                  |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                          |
| `history`         | `dead_kingdoms`, `entity`, `founded`, `log`, `world`                                                                                   |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `relations`, `rulers`, `wars`               |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `subspecies <id>` | `breakdown`, `leaders`, `metadata`, `pop`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                                           |
| `tiles <x,y>`     | `actors`, `distances`, `ground`, `islet`, `owner`, `rays`, `tile_info`                                                                 |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                                   |
| `world`           | `boats`, `cumulative`, `laws`, `leaders`, `lineages`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`                            |

## Gloses :

`python tools/gloss/info.py <clé>` glose un champ en une ligne ; une balise **`gloss:<clé>`** y renvoie, comme `wiki:` au wiki. La clé suit la sortie, `<outil>.<section>.<champ>`, ou le champ seul s'il sert à plusieurs ; un fragment suffit (`pairings` rend la section entière). Avant de lire une section, `gloss <outil>.<section>` rend ses gloses, champs partagés compris, `gloss <outil>` tout l'outil ; plusieurs par virgules, chaque glose une fois.

## Options :

### Partagées :

- `--sapient`, `--beasts` : sous `world … lineages`, `pairings` et `roster`
- `--since C<n>` : ce qui a bougé depuis, sous `actor` (`gloss:actor.since`, `gloss:to.then`), `geography` en soldes (`gloss:geography.since`), `history log` et `world … roster`
- `-i <id>` : une terre, ou `islets` et `water` là où on les compte (`geography`, `world … roster`) ; sous `tiles`, `gloss:to_island`
- `-w <eau>` : `lake<id>`, `river<id>` ou `sea<id>` ; sous `geography … waters`, une famille (`lake`…) ; sous `tiles`, `gloss:to_body`

### `actor` :

- `--statuses` : ses statuts, par chapitre (`gloss:actor.statuses`)
- `--to <p<id> | x,y | b<id> | c<id> | cities | i<terre> | lands | "<lieu>" | lake4 | burning | type>` : une cité par son centre, les cités et les terres qu'il peut gagner, un nom de `places.json` (`gloss:to.place`), la flamme la plus proche, ou le plus proche de chaque type, famille, ressource, sol, gel (`frozen`) ou eau (`lake`, `water`…), `g:<sol>` un sol, même au nom d'un type, par virgules pour ceux-là seuls ; répété, chacun à part. `gloss:actor.to`.

### `geography` :

- `-t <type>` : sous `positions`, types, familles (`trees`…, `homes` les toits) et ressources, par virgules, hors corps ; sous `biomes`, un biome ou un sol (`gloss:biomes`)

### `history` :

- `entity <type> <id>` : les années d'une entité
- `founded` : ce que le journal tait (`gloss:history.founded`)
- `log` : `--actor <id>` celles d'un corps, `-t <event>` un type
- `world` : `gloss:history.world`

### `kingdom` :

- `relations --kingdom <id>[,<id>]` : envers ceux-là seuls

### `tiles` :

- `-g <sol>` : `gloss:to_ground`
- `--to <x,y>` : cap et mesures, sous `to` si une section la rejoint ; à chaque bout, `--to` seul, un bâtiment `b<id>` (au plus proche), une cité `c<id>` (son centre), un corps `p<id>`, une eau `lake<id>` ou un `"<lieu>"` (`gloss:to.from`)

### `world` :

- `laws` : les lois par leur libellé du jeu, celui de `wiki:World_Laws`
- `lineages`, `pairings` : `-t` une espèce (`gloss:lineages`, `gloss:pairings`)
- `roster` : chaque vivant ; `-t` type ou famille, `--trait`, `--has`/`--lacks <compte>`, `--rank <mesure> [n]`, `--nearest <x,y | p<id>>`, `--with <champs>`, 4 au plus, d'`actor … stats` ou d'une fiche, `--status`/`--task <id>`, `--stage <palier>`, `--bred` les nés d'un corps, `--settle` (`settle` vrai ou `child`), `--barred` l'inverse, `--patch <x,y>` sa parcelle, `--<entité> <id>` (`--city`…) ses membres, `--job <métier>` (`king`…). `gloss:roster`.

---

## Carte :

`tools/map/show.py <x,y> [C<n>]` — cerne la tuile sur la carte du chapitre, rend le chemin de l'image. `--zoom <n>` : les n tuiles autour — **à lire toi-même** pour la forme d'une côte —, leurs parts en dessous, chaque sol nommé comme dans `biomes`, puis les tuiles en feu, la neige d'une roche, la glace et le gel.

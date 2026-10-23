# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 23/10/26 12:42</p>

Chaque outil : `python tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON ou un `✗` seul sur stderr, qui refuse l'appel ou dit qu'il n'y a rien (`no … in this world` est une réponse, pas une panne), citée en abrégé : `kingdom … metadata`. Ses coordonnées croissent vers l'est (x) et le nord (y), un `dir` aussi. Un seul bloc nommé (une section, `--to`, une tuile) sort nu ; plusieurs gardent leur clé. Ce que fixe un filtre (`-i`, un seul `-t`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre. Un compte à 0 et un drapeau faux se taisent : absent, il vaut 0 — ou 1 (`gen`, `level`, `past_chiefs`), `normal` (taxe). `sections` = liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … laws`, `pairings` et `roster`, à nommer) ; le suffixe **`C<n>`** lit ce chapitre ; sans lui, le dernier.

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
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `islet`, `tile_info`                                                                       |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                                   |
| `world`           | `boats`, `cumulative`, `laws`, `leaders`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`                                        |

## Gloses :

`python tools/gloss/info.py <clé>` glose un champ en une ligne ; une balise **`gloss:<clé>`** y renvoie, comme `wiki:` au wiki. La clé suit la sortie, `<outil>.<section>.<champ>`, ou le champ seul s'il sert à plusieurs ; un fragment suffit (`pairings` rend la section entière). Avant de te servir d'un outil, `gloss <outil>` rend toutes ses gloses, les champs partagés compris.

## Options :

### `actor` :

- `--since C<n>` : ce qui a bougé depuis (`gloss:actor.since`, `gloss:to.then`)
- `--kills` : ses morts données, par chapitre (`gloss:actor.kills`)
- `--statuses` : ses statuts durables, par chapitre (`gloss:actor.statuses`)
- `--to <p<id> | x,y | b<id> | c<id> | i<terre> | type>` : un corps, une tuile, un bâtiment, une cité (son centre), une terre ou le plus proche de chaque type, famille ou ressource, par virgules pour les seuls types ; répété, chacun sous ses mots. `gloss:actor.to`.

### `geography` :

- `--since C<n>` : ce qui a bougé, en soldes (`gloss:geography.since`)
- `-i <id>` : une seule terre dans les sections rangées par terre, ou `islets` et `water` là où elles les comptent
- `-t <type>` : sous `positions`, types, familles (`trees`…) et ressources, par virgules, hors corps ; sous `biomes`, un biome ou un sol (`gloss:biomes`)

### `history` :

- `entity <type> <id>` : les années d'une entité
- `log` : `--since C<n>` depuis un chapitre, `--actor <id>` les entrées qui nomment un corps, `-t <event>` un type (`kingdom_new`…)

### `tiles` :

- `-g <sol>` : un sol tel que `biomes` le nomme (`gloss:to_ground`)
- `-i <id>` : une terre par son id (`gloss:to_island`)
- `-r <n>` : rayon — `distances` : la tuile demandée seule ; **2 au plus, à dessein** : au-delà, des centaines de fiches noieraient ce qu'on cherche — les abords se lisent par `map/show.py --zoom`, `geography burning -i`, `distances -w`/`-g`
- `--to <x,y>` : cap et mesures entre lieux, sous `to` si une section la rejoint ; pas avec `-r` ; à chaque bout, `--to` seul, un bâtiment `b<id>` (au plus proche), une cité `c<id>` (son centre) ou un corps `p<id>`
- `-w <eau>` : une eau par son id, `lake<id>`, `river<id>` ou `sea<id>` (`gloss:to_body`)

### `world` :

- `laws` : les lois par leur libellé du jeu, celui de `wiki:World_Laws`
- `pairings` : par espèce, la 1ʳᵉ naissance au plus tôt et son couple. `gloss:pairings`.
- `roster` : chaque vivant ; `-t` type ou famille, `--trait`, `--has`/`--lacks <compte>`, `--top <mesure>`, `--nearest <x,y | p<id>>` les plus proches à vol d'oiseau, `--with <champs>` jusqu'à 4, d'`actor … stats` ou d'une fiche, `--status`/`--task <id>`, `--sapient`, `--settle` (`settle` vrai ou `child`) et `--barred`, l'inverse, `-i` une terre, `islets` ou `water`, `--patch <x,y>` sa parcelle, `--<entité> <id>` (`--city`, `--army`…) ses membres, `--since C<n>` ce qui a changé. `gloss:roster`.

---

## Carte :

`map/show.py <x,y> [C<n>]` — cerne la tuile sur la carte du chapitre, rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**. `--zoom <n>` : les n tuiles autour — **à lire toi-même** pour la forme d'une côte —, leurs parts d'eau, de sol et de roche en dessous.

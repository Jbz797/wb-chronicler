# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 09/11/26 23:06</p>

Chaque outil : `python tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON ou un `✗` seul sur stderr, qui refuse l'appel ou dit qu'il n'y a rien (`no … in this world` est une réponse, pas une panne) ; une réponse partielle dit là, d'un `⚠`, ce qu'elle laisse, son JSON entier sur stdout, et une ligne `·` informe sans rien retirer ; citée en abrégé : `kingdom … metadata`.

- **Un champ absent vaut rien** : un compte à 0, un drapeau faux, une liste ou un bloc vides se taisent, sauf où une glose dit le contraire ; absent, un compte vaut 0, ou 1 (`gen`, `level`, `past_chiefs`), `normal` (taxe) ; sauf sous `roster --with`, qui chasse du socle autant de champs qu'il en ajoute (`gloss world.--with`) : omis, pas nuls.
- **Ce que fixe un filtre** (une terre `i<id>`, un seul `type:`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre.
- **`sections`** : liste à virgules (`full` par défaut = toutes, sauf `geography` et `world … laws`, à nommer) ; un bloc nommé seul (section, `--to`, tuile) sort nu, plusieurs gardent leur clé.
- **Le suffixe `C<n>`** lit ce chapitre ; sans lui, le dernier ; l'outil `across` pose la question à chacun, rangée par chapitre (`across C1-C9 world metadata --keep date` : la date de chacun).
- **Une sortie se lit entière** : coupée (`head`), le JSON ne se lit plus ; les sections lourdes, une à une. Trop longue, une liste se coupe, la coupe dite d'un `⚠` : le reste se demande par `--limit` ou ses filtres (`--filter i<id>`, `-t`, une section).

| Commande          | Sections                                                                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `actor <id>`      | `companions`, `crafted`, `died`, `gear`, `inventory`, `kin`, `metadata`, `plot`, `ranks`, `stats`, `surroundings`, `traits`, `victims` |
| `alliance <id>`   | `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `pop`, `ranks`, `wars`                                                     |
| `boat <id>`       | `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                        |
| `book <id>`       | `gains`, `metadata`, `origin`, `teaches`                                                                                               |
| `city <id>`       | `army`, `books`, `breakdown`, `buildings`, `gear`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `pop`, `ranks`, `rulers` |
| `clan <id>`       | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                               |
| `culture <id>`    | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `family <id>`     | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`                                                                         |
| `geography`       | `biomes`, `bodies`, `burning`, `clouds`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `ridges`, `totals`, `waters`        |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                          |
| `history`         | `dead_kingdoms`, `entity`, `founded`, `log`, `rulers`, `world`                                                                         |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `relations`, `rulers`, `wars`               |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `subspecies <id>` | `breakdown`, `leaders`, `metadata`, `pop`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                                           |
| `tiles <x,y>`     | `actors`, `distances`, `ground`, `islet`, `owner`, `rays`, `tile_info`                                                                 |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                                   |
| `world`           | `boats`, `cumulative`, `laws`, `leaders`, `metadata`, `plots`, `snapshot`                                                              |

- **La carte** : `tools/map/show.py <x,y> [C<n>]` cerne la tuile sur la carte du chapitre et rend le chemin de l'image ; `gloss map.--zoom` pour lire une côte.
- **Une liste** : `--roster`, une ligne par corps (`actor`), couronne (`kingdom`) ou lignée (`subspecies`) ; une espèce : `actor --roster --filter type:<espèce>`.

## Gloses :

`python tools/gloss/info.py <clé>` glose un champ ou une option ; une balise **`gloss:<clé>`** y renvoie, comme `wiki:` au wiki. La clé suit la sortie, `<outil>.<section>.<champ>`, une option `<outil>.--<option>`, ou le champ seul, l'option seule, s'ils servent à plusieurs (`--since`). Avant de lire une section, `gloss <outil>.<section>` rend ses gloses, `gloss <outil>` tout l'outil ; plusieurs par virgules, chaque glose une fois.

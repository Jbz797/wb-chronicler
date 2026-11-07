# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 07/11/26 02:16</p>

Chaque outil : `python tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON ou un `✗` seul sur stderr, qui refuse l'appel ou dit qu'il n'y a rien (`no … in this world` est une réponse, pas une panne), citée en abrégé : `kingdom … metadata`.

- **Un champ absent vaut rien** : un compte à 0, un drapeau faux, une liste ou un bloc vides se taisent, sauf où une glose dit le contraire ; absent, un compte vaut 0, ou 1 (`gen`, `level`, `past_chiefs`), `normal` (taxe).
- **Ce que fixe un filtre** (`-i`, un seul `-t`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre.
- **Les coordonnées** croissent vers l'est (x) et le nord (y), un `dir` aussi.
- **`sections`** : liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … laws`, `lineages`, `pairings` et `roster`, à nommer) ; un bloc nommé seul (section, `--to`, tuile) sort nu, plusieurs gardent leur clé.
- **Le suffixe `C<n>`** lit ce chapitre ; sans lui, le dernier ; l'outil `across` pose la question à chacun, rangée par chapitre (`across C1-C9 world metadata --keep date` : la date de chacun).
- **`--help`** donne la syntaxe d'un outil : ses options, leurs arguments, leurs choix ; ce que fait chacune, sa glose.
- **Une sortie se lit entière** : coupée (`head`), le JSON ne se lit plus ; les sections lourdes, une à une. Trop large, elle se résume (un compte par terre) : le détail se demande par ses filtres (`-i`, `-t`, une section).

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
| `history`         | `dead_kingdoms`, `entity`, `founded`, `log`, `world`                                                                                   |
| `kingdom [<id>]`  | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `relations`, `rulers`, `wars`               |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `subspecies <id>` | `breakdown`, `leaders`, `metadata`, `pop`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                                           |
| `tiles <x,y>`     | `actors`, `distances`, `ground`, `islet`, `owner`, `rays`, `tile_info`                                                                 |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                                   |
| `world`           | `boats`, `cumulative`, `laws`, `leaders`, `lineages`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`                            |

- **La carte** : `tools/map/show.py <x,y> [C<n>]` cerne la tuile sur la carte du chapitre et rend le chemin de l'image ; `gloss map.--zoom` pour lire une côte.

## Gloses :

`python tools/gloss/info.py <clé>` glose un champ ou une option en une ligne ; une balise **`gloss:<clé>`** y renvoie, comme `wiki:` au wiki. La clé suit la sortie, `<outil>.<section>.<champ>`, une option `<outil>.--<option>` (`world.--rank`), ou le champ seul, l'option seule, s'ils servent à plusieurs (`--since`) ; un fragment suffit (`pairings` rend la section entière). Avant de lire une section, `gloss <outil>.<section>` rend ses gloses, `gloss <outil>` tout l'outil, options et champs partagés compris ; plusieurs par virgules, chaque glose une fois.

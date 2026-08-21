# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 21/08/26 19:53</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, un champ `info` le signale, et la clé qui porte le bloc nomme la section à demander. Un préfixe `top_` ne tronque pas mais change de mesure : `top_drivers` ne garde que les deux extrêmes et ne somme à rien, quand la section rend le `drivers` complet, qui somme au `total`.

| Commande                           | Sections                                                                                                                                       |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `companions`, `creature_traits`, `equipment`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`                             |
| `boat/info.py <id>`                | `full`, `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                        |
| `book/info.py <id>`                | `full`, `gains`, `metadata`, `origin`, `teaches`                                                                                               |
| `building/info.py <id>`            | `full`, `boats`, `inventory`, `metadata`, `occupants`                                                                                          |
| `city/info.py <id>`                | `full`, `army`, `books`, `breakdown`, `equipment`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `population`, `ranks`            |
| `clan/info.py <id>`                | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                             |
| `culture/info.py <id>`             | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                    |
| `family/info.py <id>`              | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`                                                       |
| `geography/info.py`                | `full`, `islands`, `natural_features`                                                                                                          |
| `kingdom/info.py <id>`             | `full`, `alliance`, `boats`, `breakdown`, `cities`, `equipment`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `wars` |
| `language/info.py <id>`            | `full`, `books`, `breakdown`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `speakers`, `traits`                                   |
| `religion/info.py <id>`            | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                    |
| `subspecies/info.py <id>`          | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`             |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `buildings`, `context`, `distances`, `tile_info`                                                                             |
| `world/info.py`                    | `full`, `boats`, `cumulative`, `leaders`, `metadata`, `snapshot`                                                                               |

##### Options :

- `r` : rayon

##### Nouveau chapitre :

`chapter/new.py` — crée le chapitre suivant depuis le save live ; le cycle complet (garde-fous, ce que le chroniqueur remplit ensuite) est décrit dans `chronicler.md`.

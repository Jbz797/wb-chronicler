# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 17/08/26 20:41</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, elle porte un champ `info` qui pointe vers sa forme complète — inutile de deviner lesquelles s'allègent, la sortie le dit. Une clé préfixée `top_` signale la même troncature à l'intérieur d'une entrée.

| Commande                           | Sections                                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `companions`, `creature_traits`, `equipment`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`                    |
| `city/info.py <id>`                | `full`, `army`, `books`, `breakdown`, `equipment`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `population`, `ranks`   |
| `clan/info.py <id>`                | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                    |
| `family/info.py <id>`              | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`                                              |
| `geography/info.py`                | `full`, `islands`, `natural_features`                                                                                                 |
| `house/info.py <id>`               | `full`, `inventory`, `metadata`, `occupants`                                                                                          |
| `kingdom/info.py <id>`             | `full`, `alliance`, `breakdown`, `cities`, `equipment`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `wars` |
| `subspecies/info.py <id>`          | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`    |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `buildings`, `context`, `distances`, `tile_info`                                                                    |
| `world/info.py`                    | `full`, `cumulative`, `leaders`, `metadata`, `snapshot`                                                                               |

##### Options :

- `r` : rayon

##### Nouveau chapitre :

`chapter/new.py` — crée le chapitre suivant depuis le save live ; le cycle complet (garde-fous, ce que le chroniqueur remplit ensuite) est décrit dans `chronicler.md`.

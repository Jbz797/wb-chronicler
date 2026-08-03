# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 03/08/26 01:27</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

Nommer une section, c'est la vouloir en profondeur : elle sort avec son détail complet, là où `full` en donne parfois une forme résumée.

| Commande                           | Sections                                                                                                                   |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `companions`, `creature_traits`, `equipment`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`         |
| `city/info.py <id>`                | `full`, `army`, `breakdown`, `equipment`, `identity`, `inventory`, `loyalty`, `metadata`, `population`, `ranks`            |
| `geography/info.py`                | `full`, `islands`, `natural_features`                                                                                      |
| `kingdom/info.py <id>`             | `full`, `alliance`, `breakdown`, `cities`, `equipment`, `identity`, `metadata`, `population`, `ranks`, `relations`, `wars` |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `buildings`, `context`, `distances`, `tile_info`                                                         |
| `world/info.py`                    | `full`, `cumulative`, `leaders`, `metadata`, `snapshot`                                                                    |

##### Options :

- `r` : rayon

##### Nouveau chapitre :

`chapter/new.py` — crée le chapitre suivant depuis le save live ; le cycle complet (garde-fous, ce que le chroniqueur remplit ensuite) est décrit dans `chronicler.md`.

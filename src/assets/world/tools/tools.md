# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 22/07/26 09:19</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

| Commande                           | Sections                                                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `best_friend`, `creature_traits`, `equipment`, `inventory`, `lover`, `metadata`, `plot`, `ranks_in_species`, `stats` |
| `city/info.py <id>`                | `full`, `breakdown`, `metadata`, `population`, `ranks`                                                                       |
| `geography/info.py`                | `full`, `islands`, `natural_features`                                                                                        |
| `kingdom/info.py <id>`             | `full`, `alliance`, `breakdown`, `cities`, `metadata`, `population`, `ranks`, `relations`, `wars`                            |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `buildings`, `context`, `distances`, `tile_info`                                                           |
| `world/info.py`                    | `full`, `cumulative`, `leaders`, `metadata`, `snapshot`                                                                      |

##### Options :

- `r` : rayon

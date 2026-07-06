# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 03/07/26 15:47</p>

Invoquer chaque script via `python3 tools/<commande> [sections]`. Sortie : objet JSON sur `stdout`. `sections` accepte une liste séparée par des virgules — `full` (défaut) renvoie toutes les sections.

| Commande                           | Sections                                                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `best_friend`, `creature_traits`, `equipment`, `inventory`, `lover`, `metadata`, `plot`, `ranks_in_species`, `stats` |
| `geography/info.py`                | `islands`, `natural_features`                                                                                                |
| `kingdom/info.py <id>`             | `full`, `metadata`, `population`, `ranks`, `relations`, `wars`                                                               |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `buildings`, `context`, `distances`, `tile_info`                                                           |
| `world/info.py`                    | `full`, `cumulative`, `metadata`, `snapshot`                                                                                 |

##### Options :

- `r` : rayon

# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 13/07/26 11:44</p>

Invoquer chaque script via `python3 tools/<commande> [sections]`. Sortie : objet JSON sur `stdout`. `sections` accepte une liste séparée par des virgules — `full` (défaut) renvoie toutes les sections.

| Commande                           | Sections                                                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `best_friend`, `creature_traits`, `equipment`, `inventory`, `lover`, `metadata`, `plot`, `ranks_in_species`, `stats` |
| `geography/info.py`                | `islands`, `natural_features`                                                                                                |
| `kingdom/info.py <id>`             | `full`, `metadata`, `population`, `ranks`, `relations`, `wars`                                                               |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `buildings`, `context`, `distances`, `tile_info`                                                           |
| `world/info.py`                    | `full`, `cumulative`, `leaders`, `metadata`, `snapshot`                                                                      |

##### Options :

- `r` : rayon

##### Sorties de `world/info.py full` :

| Section        | Champ                    | UI  | Visible à 0 | Delta |
| -------------- | ------------------------ | --- | ----------- | ----- |
| `cumulative`   | `alliances_made`         | ❌  | —           | —     |
| `cumulative`   | `armies_created`         | ❌  | —           | —     |
| `cumulative`   | `books_burnt`            | ✅  | ❌          | ✅    |
| `cumulative`   | `books_read`             | ✅  | ❌          | ✅    |
| `cumulative`   | `cities_conquered`       | ✅  | ❌          | ✅    |
| `cumulative`   | `cities_created`         | ❌  | —           | —     |
| `cumulative`   | `cities_rebelled`        | ✅  | ❌          | ✅    |
| `cumulative`   | `clans_created`          | ❌  | —           | —     |
| `cumulative`   | `creatures_born`         | ❌  | —           | —     |
| `cumulative`   | `creatures_created`      | ❌  | —           | —     |
| `cumulative`   | `cultures_created`       | ❌  | —           | —     |
| `cumulative`   | `deaths`                 | ✅  | ❌          | ✅    |
| `cumulative`   | `evolutions`             | ✅  | ❌          | ✅    |
| `cumulative`   | `families_created`       | ❌  | —           | —     |
| `cumulative`   | `houses_built`           | ❌  | —           | —     |
| `cumulative`   | `kingdoms_created`       | ❌  | —           | —     |
| `cumulative`   | `languages_created`      | ❌  | —           | —     |
| `cumulative`   | `metamorphosis`          | ✅  | ❌          | ✅    |
| `cumulative`   | `peaces_made`            | ❌  | —           | —     |
| `cumulative`   | `plots_started`          | ❌  | —           | —     |
| `cumulative`   | `plots_succeeded`        | ✅  | ❌          | ✅    |
| `cumulative`   | `religions_created`      | ❌  | —           | —     |
| `cumulative`   | `subspecies_created`     | ❌  | —           | —     |
| `cumulative`   | `wars_started`           | ❌  | —           | —     |
| `leaders`      | `dominant_culture`       | ✅  | —           | ❌    |
| `leaders`      | `dominant_language`      | ✅  | —           | ❌    |
| `leaders`      | `dominant_religion`      | ✅  | —           | ❌    |
| `leaders`      | `dominant_subspecies`    | ✅  | —           | ❌    |
| `leaders`      | `most_populous_kingdom`  | ✅  | —           | ❌    |
| `leaders`      | `most_populous_village`  | ✅  | —           | ❌    |
| `leaders`      | `most_renowned_clan`     | ✅  | —           | ❌    |
| `leaders`      | `most_renowned_person`   | ✅  | —           | ❌    |
| `metadata`     | `age_id`                 | ✅  | —           | ❌    |
| `metadata`     | `months_until_next_age`  | ❌  | —           | —     |
| `metadata`     | `world_time`             | ✅  | ✅          | ❌    |
| `snapshot`     | `alliances`              | ✅  | ✅          | ✅    |
| `snapshot`     | `armies`                 | ✅  | ✅          | ✅    |
| `snapshot`     | `books`                  | ✅  | ✅          | ✅    |
| `snapshot`     | `buildings`              | ✅  | ✅          | ✅    |
| `snapshot`     | `cities`                 | ✅  | ✅          | ✅    |
| `snapshot`     | `clans`                  | ✅  | ✅          | ✅    |
| `snapshot`     | `cultures`               | ✅  | ✅          | ✅    |
| `snapshot`     | `equipment`              | ✅  | ✅          | ✅    |
| `snapshot`     | `families`               | ✅  | ✅          | ✅    |
| `snapshot`     | `frozen_tiles`           | ✅  | ✅          | ✅    |
| `snapshot`     | `houses`                 | ✅  | ✅          | ✅    |
| `snapshot`     | `infected`               | ✅  | ❌          | ✅    |
| `snapshot`     | `kingdoms`               | ✅  | ✅          | ✅    |
| `snapshot`     | `languages`              | ✅  | ✅          | ✅    |
| `snapshot`     | `plots_active`           | ✅  | ❌          | ❌    |
| `snapshot`     | `population`             | ✅  | ✅          | ✅    |
| `snapshot`     | `relations`              | ❌  | —           | —     |
| `snapshot`     | `religions`              | ✅  | ✅          | ✅    |
| `snapshot`     | `subspecies`             | ✅  | ✅          | ✅    |
| `snapshot`     | `trees`                  | ✅  | ✅          | ✅    |
| `snapshot`     | `vegetation`             | ✅  | ✅          | ✅    |
| `snapshot`     | `wars`                   | ✅  | ✅          | ✅    |
| `snapshot`     | `wild_creatures`         | ✅  | ✅          | ✅    |

- `Visible à 0` = affiché même à 0. `cumulative`, `deaths`, `infected` et `plots_active` ne s'affichent qu'à > 0.
- `Delta` = l'UI montre la variation vs chapitre précédent : `cumulative` + `deaths` sont rendus **en tant que** delta (« Activité récente » / « Causes de mortalité »), `snapshot` affiche valeur + delta.
- `leaders` = entités `{ id, name, value }` (« Palmarès »), badge NEW si le n°1 change. `—` = non applicable (non affiché ou non numérique).

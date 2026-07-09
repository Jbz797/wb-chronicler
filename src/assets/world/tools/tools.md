# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 09/07/26 09:41</p>

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

##### Sorties de `actor/info.py full` :

| Section               | Champ             | Rank | UI  | Visible à 0 | Delta | UI Rank |
| --------------------- | ----------------- | ---- | --- | ----------- | ----- | ------- |
| `best_friend`/`lover` | `age`             | ❌   | ✅  | ✅          | ❌    | ❌      |
| `best_friend`/`lover` | `health_max`      | ❌   | ✅  | ✅          | ❌    | ❌      |
| `best_friend`/`lover` | `id`              | ❌   | ❌  | —           | —     | —       |
| `best_friend`/`lover` | `level`           | ❌   | ✅  | ✅          | ❌    | ❌      |
| `best_friend`/`lover` | `money`           | ❌   | ✅  | ✅          | ❌    | ❌      |
| `best_friend`/`lover` | `name`            | ❌   | ✅  | —           | ❌    | ❌      |
| `best_friend`/`lover` | `renown`          | ❌   | ✅  | ✅          | ❌    | ❌      |
| `best_friend`/`lover` | `sex`             | ❌   | ✅  | —           | ❌    | ❌      |
| `creature_traits`     | `id`              | ❌   | ❌  | —           | —     | —       |
| `creature_traits`     | `description`     | ❌   | ❌  | —           | —     | —       |
| `creature_traits`     | `flavor`          | ❌   | ❌  | —           | —     | —       |
| `creature_traits`     | `rarity`          | ❌   | 🔶  | ✅          | ✅    | ❌      |
| `creature_traits`     | `stats`           | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `age`             | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `asset_id`        | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `by`              | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `durability`      | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `from`            | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `id`              | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `kills`           | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `modifiers`       | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `rarity`          | ❌   | ❌  | —           | —     | —       |
| `equipment`           | `stats`           | ❌   | ❌  | —           | —     | —       |
| `inventory`           | `{ item_id: n }`  | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `age`             | ✅   | ✅  | ✅          | ❌    | ✅      |
| `metadata`            | `asset_id`        | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `can_reproduce`   | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `city`            | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `clan`            | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `culture`         | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `family`          | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `favorite_food`   | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `generation`      | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `island_id`       | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `kingdom`         | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `language`        | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `life_stage`      | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `mass`            | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `name`            | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `personality`     | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `profession`      | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `religion`        | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `roles`           | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `sex`             | ❌   | ✅  | —           | ❌    | ❌      |
| `metadata`            | `subspecies`      | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `x`               | ❌   | ❌  | —           | —     | —       |
| `metadata`            | `y`               | ❌   | ❌  | —           | —     | —       |
| `plot`                | `name`            | ❌   | ❌  | —           | —     | —       |
| `plot`                | `progress`        | ❌   | ✅  | ✅          | ❌    | ❌      |
| `plot`                | `started_at`      | ❌   | ❌  | —           | —     | —       |
| `plot`                | `target_alliance` | ❌   | ✅  | —           | ❌    | ❌      |
| `plot`                | `target_kingdom`  | ❌   | ✅  | —           | ❌    | ❌      |
| `plot`                | `type_id`         | ❌   | ✅  | —           | ❌    | ❌      |
| `stats`               | `armor`           | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `attack_speed`    | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `birth_rate`      | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `births`          | ✅   | ❌  | —           | —     | —       |
| `stats`               | `children`        | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `critical_chance` | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `damage`          | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `damage_range`    | ✅   | ✅  | ✅          | ✅    | ❌      |
| `stats`               | `diplomacy`       | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `equipment_power` | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `happiness`       | ❌   | ✅  | ✅          | ❌    | ❌      |
| `stats`               | `health`          | ❌   | ✅  | ✅          | ❌    | ❌      |
| `stats`               | `health_max`      | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `intelligence`    | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `kills`           | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `level`           | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `lifespan`        | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `loot`            | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `mana`            | ❌   | ✅  | ✅          | ❌    | ❌      |
| `stats`               | `mana_max`        | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `max_children`    | ❌   | ✅  | ✅          | ❌    | ❌      |
| `stats`               | `money`           | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `nutrition`       | ❌   | ✅  | ✅          | ❌    | ❌      |
| `stats`               | `renown`          | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `speed`           | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `stamina`         | ❌   | ✅  | ✅          | ❌    | ❌      |
| `stats`               | `stamina_max`     | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `stewardship`     | ✅   | ✅  | ✅          | ✅    | ✅      |
| `stats`               | `warfare`         | ✅   | ✅  | ✅          | ✅    | ✅      |

- `🔶` = agrégé puis affiché

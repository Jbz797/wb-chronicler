# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 04/09/26 09:16</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes, sauf `geography` qui n'en a pas et exige une section nommée) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, un champ `info` le signale, et la clé qui porte le bloc nomme la section à demander. Un préfixe `top_` ne tronque pas mais change de mesure : `top_drivers` ne garde que les deux extrêmes et ne somme à rien, quand la section rend le `drivers` complet, qui somme au `total`.

`island_id` **absent** sur une tuile terrestre : l'îlot est trop petit pour que WorldBox le compte comme une île. Ce n'est pas une position en mer — `tiles/info.py <x,y>` le confirme.

| Commande                           | Sections                                                                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`               | `full`, `companions`, `equipment`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`, `traits`                           |
| `alliance/info.py <id>`            | `full`, `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `population`, `ranks`, `wars`                                   |
| `boat/info.py <id>`                | `full`, `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                             |
| `book/info.py <id>`                | `full`, `gains`, `metadata`, `origin`, `teaches`                                                                                    |
| `city/info.py <id>`                | `full`, `army`, `books`, `breakdown`, `equipment`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `population`, `ranks` |
| `clan/info.py <id>`                | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                  |
| `culture/info.py <id>`             | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                         |
| `family/info.py <id>`              | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`                                            |
| `geography/info.py`                | `biomes`, `entity_types`, `islands`, `positions [-t <type>]`, `waters`                                                              |
| `ground/info.py <id>`              | `full`, `boats`, `inventory`, `metadata`, `occupants`                                                                               |
| `kingdom/info.py <id>`             | `full`, `boats`, `breakdown`, `cities`, `equipment`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `wars`  |
| `language/info.py <id>`            | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                         |
| `religion/info.py <id>`            | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                         |
| `subspecies/info.py <id>`          | `full`, `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`              |
| `tiles/info.py <x,y> [-r 0\|1\|2]` | `full`, `actors`, `context`, `distances`, `ground`, `tile_info`                                                                     |
| `war/info.py <id>`                 | `full`, `attackers`, `defenders`, `metadata`                                                                                        |
| `world/info.py`                    | `full`, `boats`, `cumulative`, `leaders`, `metadata`, `plots`, `snapshot`                                                           |

##### Options :

- `r` : rayon
- `t` : type d'entité

##### Nouveau chapitre :

`chapter/new.py` — crée le chapitre suivant depuis le save live ; le cycle complet (garde-fous, ce que le chroniqueur remplit ensuite) est décrit dans `chronicler.md`.

##### Description du monde :

`chapter/new.py --description "…"` — reformule le monde sans écrire de chapitre. **WorldBox fermé**, rouvrir la save ensuite. **Force majeure seulement** : elle se pose au reset.

##### Favori :

`chapter/favorite.py <id>` — marque l'acteur favori dans la save et régénère le chapitre courant. **Après accord du joueur**, **WorldBox fermé** ; cf. « Choix du favori » dans `chronicler.md`.

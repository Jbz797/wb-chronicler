# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 14/09/26 01:37</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes, sauf `geography` qui n'en a pas et exige une section nommée) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

| Commande                   | Sections                                                                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`       | `full`, `companions`, `equipment`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`, `surroundings`, `traits`           |
| `alliance/info.py <id>`    | `full`, `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `population`, `ranks`, `wars`                                   |
| `boat/info.py <id>`        | `full`, `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                             |
| `book/info.py <id>`        | `full`, `gains`, `metadata`, `origin`, `teaches`                                                                                    |
| `city/info.py <id>`        | `full`, `army`, `books`, `breakdown`, `equipment`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `population`, `ranks` |
| `clan/info.py <id>`        | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                  |
| `culture/info.py <id>`     | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                         |
| `family/info.py <id>`      | `full`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`                                            |
| `geography/info.py`        | `biomes`, `burning`, `entity_types`, `equipment`, `frozen`, `islands`, `positions [-t]`, `waters`                                   |
| `ground/info.py <id>`      | `full`, `boats`, `inventory`, `metadata`, `occupants`                                                                               |
| `kingdom/info.py <id>`     | `full`, `boats`, `breakdown`, `cities`, `equipment`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `wars`  |
| `language/info.py <id>`    | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                         |
| `religion/info.py <id>`    | `full`, `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                         |
| `subspecies/info.py <id>`  | `full`, `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`              |
| `tiles/info.py <x,y> [-r]` | `full`, `actors`, `context`, `distances`, `ground`, `tile_info`                                                                     |
| `war/info.py <id>`         | `full`, `attackers`, `defenders`, `metadata`                                                                                        |
| `world/info.py`            | `full`, `boats`, `cumulative`, `leaders`, `metadata`, `plots`, `snapshot`                                                           |

## Options :

- `r <n>` : rayon
- `t <type>` : **un `asset_id` exact**, jamais une famille (ex. `pine_tree` répond, `tree` rend `{}` sans rien dire) ; `entity_types` donne la liste

---

## Carte :

`map/show.py <x,y>` — cerne la tuile sur la carte du chapitre courant et rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**.

## Description du monde :

`chapter/new.py --description "…"` — reformule le monde sans écrire de chapitre. **WorldBox fermé**, rouvrir la save ensuite. **Force majeure seulement** : elle se pose au reset.

## Favori :

`chapter/favorite.py <id>` — marque l'acteur favori dans la save et régénère le chapitre courant. **Après accord du joueur**, **WorldBox fermé** ; cf. « Choix du favori » dans `chronicler.md`.

## Lire les sorties :

### Formes et mesures :

- `actor … stats` rend des valeurs **déjà agrégées** — tout y est, du socle de l'espèce aux bonus de niveau : n'ajoute rien par-dessus. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié tant qu'`adult_age` n'est pas atteint, seuil que `subspecies … stats` donne pour toute la lignée, avec `breeding_age`. La valeur adulte ne s'en déduit pas pour autant : la base de la lignée n'est pas celle du corps.
- `actor … surroundings`, à vol d'oiseau : `intimate` ≤ 25 tuiles, `common` ≤ 120. `sapient` n'y paraît que vrai, `island_id` que sur une autre terre, `adrift` hors terre comptée.
- `island_id` **absent** couvre deux cas opposés : un îlot trop petit pour compter, ou l'eau. `tiles/info.py <x,y> tile_info` tranche — `kind: water` pour le second.
- `to_land` (section `distances`) mesure le bras d'eau depuis **tout le rocher**, pas depuis la tuile : un naufragé s'isole par le détroit de son île, pas par l'endroit où il se tient. Absent sur une île comptée.
- Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, un champ `info` le signale, et la clé qui porte le bloc nomme la section à demander.
- Un préfixe `top_` ne tronque pas mais change de mesure : `top_drivers` ne garde que les deux extrêmes et ne somme à rien, quand la section rend le `drivers` complet, qui somme au `total`.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents — 3 pour les cités et les royaumes. Les `leaders` d'une entité restent vides sous 4 membres, et dans `world … leaders`, `species` et `persons` ne pèsent que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers — il donne la part du ventre encore pleine, en pourcentage, donc son titulaire est celui qui en a le moins.
- Un `rank` est un rang de compétition (1, 2, 2, 4) : des ex æquo partagent la place. Un niveau 1 n'en reçoit jamais.

## Nouveau chapitre :

`chapter/new.py` — crée le chapitre suivant depuis le save live ; le cycle complet (garde-fous, ce que le chroniqueur remplit ensuite) est décrit dans `chronicler.md`.

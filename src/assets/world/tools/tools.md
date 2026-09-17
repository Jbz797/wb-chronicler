# 🛠 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 17/09/26 23:24</p>

Invoquer chaque script via `python3 tools/<commande> [sections] [C<n>]`, sortie JSON sur `stdout`. `sections` = liste séparée par des virgules (`full` par défaut = toutes, sauf `geography` qui n'en a pas et exige une section nommée) ; le suffixe optionnel **`C<n>`** (ex. `city/info.py 3 C5 metadata`) lit `saves/C<n>/map.wbox` au lieu du save live.

| Commande                   | Sections                                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `actor/info.py <id>`       | `companions`, `gear`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`, `surroundings`, `traits`                     |
| `alliance/info.py <id>`    | `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `population`, `ranks`, `wars`                                        |
| `boat/info.py <id>`        | `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                  |
| `book/info.py <id>`        | `gains`, `metadata`, `origin`, `teaches`                                                                                         |
| `city/info.py <id>`        | `army`, `books`, `breakdown`, `gear`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `population`, `ranks`, `rulers` |
| `clan/info.py <id>`        | `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                       |
| `culture/info.py <id>`     | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `family/info.py <id>`      | `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`                                                 |
| `geography/info.py`        | `biomes`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions [-t]`, `waters`                                     |
| `ground/info.py <id>`      | `boats`, `inventory`, `metadata`, `occupants`                                                                                    |
| `kingdom/info.py <id>`     | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `rulers`, `wars`  |
| `language/info.py <id>`    | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `religion/info.py <id>`    | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `subspecies/info.py <id>`  | `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                   |
| `tiles/info.py <x,y> [-r]` | `actors`, `context`, `distances`, `ground`, `tile_info`                                                                          |
| `war/info.py <id>`         | `attackers`, `defenders`, `metadata`                                                                                             |
| `world/info.py`            | `boats`, `cumulative`, `leaders`, `metadata`, `plots`, `snapshot`                                                                |

## Options :

- `-r <n>` : rayon, de 0 à 2
- `-t <type>` : **un `asset_id` exact**, jamais une famille (ex. `pine_tree` répond, `tree` rend `{}` sans rien dire) ; `entity_types` donne la liste

---

## Carte :

`map/show.py <x,y>` — cerne la tuile sur la carte du chapitre courant et rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**.

## Description du monde :

`chapter/new.py --description "…"` — reformule le monde sans écrire de chapitre. **WorldBox fermé**, rouvrir la save ensuite. **Force majeure seulement** : elle se pose au reset.

## Lire les sorties :

### Acteurs :

- `actor … metadata` : `can_reproduce` demande l'âge de reproduction et, chez qui mange, une `nutrition` d'au moins 50 ; `infertile` et `max_children` (enfants vivants) n'arrêtent que qui porte. Un mâle d'espèce sexuée n'a donc pas de `max_children` : il engendre si sa compagne peut porter. Un `false` après un `true` ne dit pas l'infertilité : une réserve entamée suffit.
- `actor … stats` rend des valeurs **déjà agrégées** — tout y est, du socle de l'espèce aux bonus de niveau (santé, mana et endurance seulement), jusqu'aux points de compétence que le corps gagne à vivre et qu'aucune autre sortie ne détaille : n'ajoute rien par-dessus. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié tant qu'`adult_age` n'est pas atteint, seuil que `subspecies … stats` donne pour toute la lignée, avec `breeding_age`. La valeur adulte ne s'en déduit pas pour autant : la base de la lignée n'est pas celle du corps.
- `actor … surroundings`, à vol d'oiseau : `intimate` ≤ 25 tuiles, `common` ≤ 120, `common_with_boat` ≤ 240 si son royaume a un bateau de transport. Une autre terre n'y paraît qu'à portée de nage (`gap` ≤ 16), ou dans le cercle du bateau ; `adrift` : dans l'eau ou sur un îlot non compté. Hors de l'intime, qui n'a ni lien, ni charge, ni meurtre, ni nom de bête se compte par cité ou par `asset_id`, sauf un pensant sans cité ou un groupe d'un seul. `life_stage` se tait à `adult`, `sapient` devant `kin`, `job` ou `role`.
- `diplomacy`, `intelligence`, `stewardship` et `warfare` (« Martial » en jeu) sont des savoirs : `warfare` dit ce qu'un corps sait de la guerre, pas la force de ses coups, qui se lit dans `damage_*` (un cinquième du `warfare` y entre).

### Formes et mesures :

- `city … rulers` et `kingdom … rulers` donnent la succession, datée comme en jeu — le premier d'un royaume l'a fondé ; bourse du souverain en place : `population.ruler_money`.
- `geography … frozen` compte la glace posée sur le sol (`frozen_tiles`), pas le biome `permafrost`, gelé par nature : une part « gelée » s'entend hors permafrost, que `biomes` donne à part.
- `island_id` **absent** couvre deux cas opposés : un îlot trop petit pour compter, ou l'eau. `tiles/info.py <x,y> tile_info` tranche — `kind: water` pour le second.
- `to_islands` (section `distances`, tuile demandée seule) donne les 10 îles les plus proches, de la plus proche à la plus lointaine, par leur **tuile la plus proche** : un centroïde se trompe de tranche.
- `to_land` (section `distances`) mesure le bras d'eau depuis **tout le rocher**, pas depuis la tuile : un naufragé s'isole par le détroit de son île, pas par l'endroit où il se tient. Absent sur une île comptée.
- `to_nearest_city` (section `distances`) vise le **quartier** le plus proche, pas le centre : on touche une ville par son bord. `to_capital` vise le centre de la capitale, et ne paraît qu'en cité.
- `world … metadata` : `months_until_next_age` est **déjà en mois**, 12 par an — il ne repasse pas par le `/ 5` d'un `world_time`.
- Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, un champ `info` le signale, et la clé qui porte le bloc nomme la section à demander.
- Sous 4 membres, un corps ne rend ni `breakdown` ni ratio par tête (`fed_pct`, `housed_pct`, `*_per_capita`) : une seule âme y pèserait le quart ou plus.
- Un écart entre deux `snapshot` est un solde, jamais un compte d'événements : ce qui est né et ce qui s'est éteint se lisent dans `cumulative`, où chaque compteur ne fait que monter.
- Un préfixe `top_` ne tronque pas mais change de mesure : `top_drivers` ne garde que les deux extrêmes et ne somme à rien, quand la section rend le `drivers` complet, qui somme au `total`.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents — 3 pour les cités et les royaumes. Les `leaders` d'une entité restent vides sous 4 membres, et dans `world … leaders`, seul `persons` ne pèse que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers — il donne la part du ventre encore pleine, en pourcentage, donc son titulaire est celui qui en a le moins.
- Un `rank` est un rang de compétition (1, 2, 2, 4), ex æquo compris. Aucun pour un niveau 1, une seule cité, un seul royaume, ni une valeur que partage plus de la moitié du vivier.

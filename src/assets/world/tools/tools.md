# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 21/09/26 16:43</p>

Invoquer chaque outil via `python3 tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON sur `stdout` — la colonne _Commande_ en donne le `<nom> [arg]`, et une sortie se cite ici en abrégé, `kingdom … metadata`. `sections` = liste séparée par des virgules (`full` par défaut = toutes, sauf `geography` qui n'en a pas et exige une section nommée) ; le suffixe optionnel **`C<n>`** (ex. `city 3 C5 metadata`) lit `saves/C<n>/map.wbox` ; sans lui, le dernier chapitre.

| Commande          | Sections                                                                                                                         |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `actor <id>`      | `companions`, `gear`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`, `surroundings`, `traits`                     |
| `alliance <id>`   | `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `population`, `ranks`, `wars`                                        |
| `boat <id>`       | `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                  |
| `book <id>`       | `gains`, `metadata`, `origin`, `teaches`                                                                                         |
| `city <id>`       | `army`, `books`, `breakdown`, `gear`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `population`, `ranks`, `rulers` |
| `clan <id>`       | `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                                       |
| `culture <id>`    | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `family <id>`     | `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`                                                 |
| `geography`       | `biomes`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `totals`, `waters`                                |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                    |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `rulers`, `wars`  |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `subspecies <id>` | `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                   |
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `tile_info`                                                                          |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                             |
| `world`           | `boats`, `cumulative`, `leaders`, `metadata`, `plots`, `snapshot`                                                                |

## Options :

### `geography … positions` :

- `-t <type>` : **un `asset_id` exact**, jamais une famille (ex. `pine_tree` répond, `tree` rend `{}` sans rien dire) ; `entity_types` donne la liste

### `tiles` :

- `-i <id>` : une terre par son id (`geography … islands`), mesurée dans `distances` comme `to_islands`, sous `to_island` : pour une terre hors des 5 plus proches — celle où l'on se tient vaut 0
- `-r <n>` : rayon, de 0 à 2 — `distances` ne répond que pour la tuile demandée, ses voisines ne diraient rien d'autre
- `--to <x,y>` : une seconde tuile, lue comme la première, et une clé `to` qui porte la marche et le cap depuis la première : la seule mesure entre deux points quelconques ; ne se combine pas avec `-r`

---

## Carte :

`map/show.py <x,y>` — cerne la tuile sur la carte du chapitre courant et rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**.

## Lire les sorties :

### Acteurs :

- `actor … metadata` : `can_reproduce` demande l'âge de reproduction et, chez qui mange, une `nutrition` d'au moins 50 ; `infertile` et `max_children` (enfants vivants) n'arrêtent que qui porte. Un mâle d'espèce sexuée n'a donc pas de `max_children` : il engendre si sa compagne peut porter. Un `false` après un `true` ne dit pas l'infertilité : une réserve entamée suffit. Ce qui ouvre ou ferme une naissance : `wiki:Reproduction`.
- `actor … stats` rend des valeurs **déjà agrégées** — tout y est, du socle de l'espèce aux bonus de niveau (santé, mana et endurance seulement), jusqu'aux points de compétence que le corps gagne à vivre — le niveau, lui, vient de l'expérience : n'ajoute rien par-dessus. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié tant qu'`adult_age` n'est pas atteint, seuil que `subspecies … stats` donne pour toute la lignée, avec `breeding_age`. La valeur adulte ne s'en déduit pas pour autant : la base de la lignée n'est pas celle du corps.
- `actor … surroundings`, en tuiles marchées : `intimate` ≤ 25 tuiles, `common` ≤ 120, `common_with_boat` ≤ 240 si son royaume a un bateau de transport. Une autre terre n'y paraît qu'à portée de nage du corps, ou dans le cercle du bateau ; `adrift` : dans l'eau ou sur un îlot non compté. Hors de l'intime, qui n'a ni lien, ni charge, ni meurtre, ni nom de bête se compte par cité ou par `asset_id`, sauf un pensant sans cité ou un groupe d'un seul. `life_stage` se tait à `adult`, `sapient` devant `kin`, `job` ou `role`.
- `diplomacy`, `intelligence`, `stewardship` et `warfare` (« Martial » en jeu) sont des savoirs : `diplomacy` et `stewardship` ne servent qu'aux rois et aux chefs, et `damage_*` dit la force d'un coup, `warfare` compris. Le reste : `wiki:Unit_Stats`.

### Formes et mesures :

- `city … rulers` et `kingdom … rulers` donnent la succession, datée comme en jeu — le premier d'un royaume l'a fondé ; bourse du souverain en place : `population.ruler_money`.
- `geography … frozen` compte la glace posée sur le sol (`frozen_tiles`), pas le biome `permafrost`, gelé par nature : une part « gelée » s'entend hors permafrost, que `biomes` donne à part.
- `geography … waters` cesse de lister un bras au-delà de toute nage : ce qui n'y figure pas, personne ne le franchit, et ses `lakes` s'arrêtent sous 64 tuiles — l'inverse ne se déduit ni de l'un ni de l'autre : une mare plus petite n'y paraît pas.
- `houses` (cité, royaume) compte les chantiers, comme le jeu : `ground … metadata` les signale par `under_construction`.
- `island_id` **absent** couvre deux cas opposés : un îlot trop petit pour compter, ou l'eau. `tiles … tile_info` tranche — `kind: water` pour le second.
- `kingdom … metadata` porte `ferries` quand la couronne tient une coque de transport : une seule suffit, et elle sert tout le royaume — la cité qui l'abrite n'y change rien.
- `religion … metadata` : `cities` et `kingdoms` comptent qui l'a faite sienne, pas où vivent ses fidèles : une cité ne la prend que si son chef y croit, un royaume que si son roi la décrète.
- `to_islands` (section `distances`) donne les 5 îles les plus proches, dans l'ordre, par leur **tuile la plus proche** : un centroïde se trompe de tranche.
- `to_land` (section `distances`) mesure le bras d'eau depuis **tout le rocher**, pas depuis la tuile : un naufragé s'isole par le détroit de son île, pas par l'endroit où il se tient. Absent sur une île comptée.
- `to_nearest_city` (section `distances`) vise le **quartier** le plus proche, pas le centre : on touche une ville par son bord. `to_capital` vise le centre de la capitale, et ne paraît qu'en cité.
- `world … metadata` : `months_until_next_age` est **déjà en mois**, 12 par an — il ne repasse pas par le `/ 5` d'un `world_time`.
- Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, un champ `info` le signale, et la clé qui porte le bloc nomme la section à demander.
- Sous 4 membres, un corps ne rend ni `breakdown` ni ratio par tête (`fed_pct`, `housed_pct`, `*_per_capita`) : une seule âme y pèserait le quart ou plus.
- Un écart entre deux `snapshot` est un solde, jamais un compte d'événements : ce qui est né et ce qui s'est éteint se lisent dans `cumulative`, où chaque compteur ne fait que monter.
- Un préfixe `top_` ne tronque pas mais change de mesure : `top_drivers` ne garde que les deux extrêmes et ne somme à rien, quand la section rend le `drivers` complet, qui somme au `total`.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents — 3 pour les cités et les royaumes. Dans `world … leaders`, seul `persons` ne pèse que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers — il donne la part du ventre encore pleine, en pourcentage, donc son titulaire est celui qui en a le moins.
- Un `rank` est un rang de compétition (1, 2, 2, 4), ex æquo compris. Aucun pour un niveau 1, une seule cité, un seul royaume, ni une valeur que partage plus de la moitié du vivier.

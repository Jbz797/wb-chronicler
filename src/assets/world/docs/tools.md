# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 24/09/26 22:54</p>

Invoquer chaque outil via `python3 tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON — la colonne _Commande_ en donne le `<nom> [arg]`, et une sortie se cite ici en abrégé, `kingdom … metadata`. `sections` = liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … pairings` et `roster`, à nommer) ; le suffixe optionnel **`C<n>`** lit `saves/C<n>/map.wbox` ; sans lui, le dernier chapitre.

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
| `geography`       | `biomes`, `bodies`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `ridges`, `totals`, `waters`            |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                    |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `rulers`, `wars`  |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `subspecies <id>` | `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                   |
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `tile_info`                                                                          |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                             |
| `world`           | `boats`, `cumulative`, `leaders`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`, `timeline`                              |

## Options :

### `actor` :

- `--to <id | x,y | i<terre> | type>` : un corps, une tuile, une terre abordée au moins cher (`landing`) ou le plus proche de types et familles, par virgules (`nearest`), et une clé `to`, marchée comme `surroundings`, en `hours` et, passé un jour, en `days` haltes comprises (rien à bord) — `swim_hours` ce qu'il en nage, `widest_crossing` son plus long bras s'il passe le souffle ; seule sans section nommée
- `--since C<n>` : ce qui a bougé depuis, dans `since` — `moved` est le trajet fait, quand `--to` ne donne qu'un gisement

### `geography` :

- `-i <id>` : une seule terre dans les sections rangées par terre
- `-t <type>` (`positions`) : un `asset_id`, une famille (`trees`…) ou une liste à virgules, hors corps

### `tiles` :

- `-i <id>` : une terre par son id, mesurée comme `to_islands` sous `to_island`, même hors des 5 plus proches — celle où l'on se tient vaut 0
- `-r <n>` : rayon, de 0 à 2 — `distances` ne répond que pour la tuile demandée
- `--to <x,y>` : une clé `to`, cap et deux mesures de lieu à lieu (d'un corps : `actor`), seule sans section nommée — sinon les deux tuiles s'y joignent ; pas avec `-r`

### `world` :

- `pairings` : par espèce, la 1ʳᵉ naissance possible (`birth_on`) et l'écart d'aujourd'hui du couple
- `roster` : chaque vivant, une ligne ; `-t` type ou famille, `--trait <id>`, `-i` une terre ; `--since C<n>` : les arrivés et les `was_on` ; passé 50, un compte par espèce

---

## Carte :

`map/show.py <x,y> [C<n>]` — cerne la tuile sur la carte du chapitre et rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**. `--zoom <n>` : les n tuiles alentour, agrandies, nord en haut — **à lire toi-même** pour la forme d'une côte.

## Lire les sorties :

### Acteurs :

- `actor … metadata` : `can_reproduce` demande l'âge de reproduction et, chez qui mange, une `nutrition` d'au moins 50 ; `infertile` et `max_children` (enfants vivants) n'arrêtent que qui porte : un mâle engendre si sa compagne le peut. Ce qui ouvre ou ferme une naissance : `wiki:Reproduction`. `can_reproduce` ne sort que vrai, `breeds_on` datant l'âge qui l'ouvrira, `adult_on` la majorité. `settle`, chez un pensant : `true` s'il pourrait fonder un village là où il se tient, sinon ce qui l'en empêche (`child`, `ground 52/64: 12 water`…).
- `actor … stats` rend des valeurs **déjà agrégées** — tout y est, du socle de l'espèce aux bonus de niveau (santé, mana et endurance seulement), jusqu'aux points de compétence gagnés à vivre : n'ajoute rien par-dessus. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié jusqu'à `adult_on`. La valeur adulte ne se lit pas sur celle de la lignée. `swim` : `breath` tant que dure le souffle, `reach` noyade comprise, sur l'endurance et la santé de l'instant, et `rested` ce qui en change reposé ; `never` pour qui brûle dans l'eau, `unlimited` pour qui n'y peine pas.
- `actor … surroundings` se compte comme `walked`, au pas du corps, qui ne nage que vers une autre terre : `intimate` ≤ 25 tuiles, `common` ≤ 120, `hours` donnant leur bord à son pas ; `common_with_boat` ≤ 240 à vol d'oiseau, si son royaume a un bateau de transport ; `water` et `islet_tiles` comme dans `tiles … tile_info`. Hors de l'intime, qui n'a ni lien, ni charge, ni meurtre, ni nom de bête se compte par cité ou par `asset_id`, sauf un pensant sans cité ou un groupe d'un seul. `sapient` se tait devant `kin`, `job` ou `role`.
- `diplomacy`, `intelligence`, `stewardship` et `warfare` (« Martial » en jeu, pas « combat ») sont des savoirs : `diplomacy` et `stewardship` ne servent qu'aux rois et aux chefs, et `damage_*` dit la force d'un coup, `warfare` compris. Le reste : `wiki:Unit_Stats`.
- `happiness` (`actor … stats`) : la barre du jeu en %, 50 au neutre — heureux dès 60, malheureux sous 30.

### Formes et mesures :

- `city … rulers` et `kingdom … rulers` donnent la succession, datée comme en jeu — le premier d'un royaume l'a fondé ; bourse du souverain en place : `population.ruler_money`.
- `description` et `flavor` d'un trait disent l'ambiance, jamais l'effet : il tient dans `stats`, que `dormant` dit endormies par l'ère, le reste dans `wiki:Creature_Traits` ou `wiki:Subspecies_Traits`.
- `geography … frozen` donne, terre par terre, la part gelée puis ses tuiles : `permafrost`, le biome gelé pour toujours ; `snow` et `ice`, la neige et la glace de la carte même ; `frost`, le gel passager.
- `houses` (cité, royaume) compte les chantiers, comme le jeu : `ground … metadata` les signale par `under_construction`.
- `kingdom … metadata` porte `ferries` quand la couronne tient une coque de transport : une seule sert tout le royaume, quelle que soit sa cité.
- `religion … metadata` : `cities` et `kingdoms` comptent qui l'a faite sienne, pas où vivent ses fidèles : une cité ne la prend que si son chef y croit, un royaume que si son roi la décrète.
- `tiles … tile_info` : `block` barre la marche, que nul ne franchit à pied ; `islet_tiles`, une terre sous 300 tuiles de sol, trop petite pour compter, et sa taille ; sur l'eau, `sea`, `lake` (son id) ou `pond_tiles`, une eau close sous 64 tuiles ; `snow`, `ice` et `frozen` (le gel passager) comme dans `geography … frozen`.
- `to_islands` (`distances`) donne les 5 îles les plus proches, dans l'ordre, par leur **tuile la plus proche**.
- `to_land` (`distances`) mesure le bras d'eau depuis **tout le rocher**.
- `to_nearest_city` (`distances`) vise le **quartier** le plus proche, pas le centre. `to_capital` vise le centre de la capitale, et ne paraît qu'en cité.
- `top_drivers` ne garde que les deux extrêmes et ne somme à rien ; le `drivers` de la section, complet, somme au `total`.
- `walked` (`distances`, `to`) : l'équivalent en tuiles de plaine du temps de marche, pas une distance (elle se lit sur `tiles`) — roche, lave et goo contournés, sans nage, au pas d'un corps sans adaptation : sable, marais, neige et, sous Entanglewood, arbres l'allongent. Absente sans terre qui les joigne.
- `world … metadata` : `months_until_next_age` est **déjà en mois**, 12 par an — il ne repasse pas par le `/ 5` d'un `world_time`.
- `world … timeline` : ce que chaque année a vu naître, mourir ou s'éteindre, l'année en cours marquée `so_far` ; une année absente n'a rien vu bouger, et la fenêtre en tient une vingtaine ; de quoi meurent les siens : `deaths_by_cause`, au `metadata` d'une cité, d'un royaume, d'un clan ou d'une sous-espèce.
- Sous 4 membres, un corps ne rend ni `breakdown` ni ratio par tête (`fed_pct`, `housed_pct`, `*_per_capita`).
- Un écart entre deux `snapshot` est un solde, jamais un compte d'événements : ce qui est né et ce qui s'est éteint se lisent dans `cumulative`, où chaque compteur ne fait que monter.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents — 3 pour les cités et les royaumes. Dans `world … leaders`, seul `persons` ne pèse que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers : la part du ventre encore pleine, en %, dont le titulaire a le moins.
- Un `rank` est un rang de compétition (1, 2, 2, 4), ex æquo compris. Aucun pour un niveau 1, une seule cité, un seul royaume, ni une valeur que partage plus de la moitié du vivier.

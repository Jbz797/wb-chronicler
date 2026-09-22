# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 22/09/26 11:22</p>

Invoquer chaque outil via `python3 tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON — la colonne _Commande_ en donne le `<nom> [arg]`, et une sortie se cite ici en abrégé, `kingdom … metadata`. `sections` = liste séparée par des virgules (`full` par défaut = toutes, sauf `geography` qui n'en a pas et exige une section nommée) ; le suffixe optionnel **`C<n>`** lit `saves/C<n>/map.wbox` ; sans lui, le dernier chapitre.

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
| `geography`       | `biomes`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `ridges`, `totals`, `waters`                      |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                    |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `rulers`, `wars`  |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `subspecies <id>` | `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                   |
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `tile_info`                                                                          |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                             |
| `world`           | `boats`, `cumulative`, `leaders`, `metadata`, `plots`, `snapshot`                                                                |

## Options :

### `actor` :

- `--to <id | x,y>` : un second corps ou une tuile, et une clé `to` comme dans `tiles`, marchée comme `surroundings`, en `hours` et, passé un jour, en `days` haltes comprises (rien à bord) ; seule sans section nommée ; l'eau qu'il ne passe pas rend une erreur chiffrée

### `geography … positions` :

- `-t <type>` : **un `asset_id` exact**, jamais une famille (ex. `pine_tree` répond, `tree` rend `{}` sans rien dire) ; `entity_types` donne la liste

### `tiles` :

- `-i <id>` : une terre par son id, mesurée comme `to_islands` sous `to_island`, même hors des 5 plus proches — celle où l'on se tient vaut 0
- `-r <n>` : rayon, de 0 à 2 — `distances` ne répond que pour la tuile demandée
- `--to <x,y>` : une seconde tuile, lue comme la première, et une clé `to` : cap et deux mesures, de lieu à lieu (d'un corps : `actor`) ; pas avec `-r`

---

## Carte :

`map/show.py <x,y>` — cerne la tuile sur la carte du chapitre courant et rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**.

## Lire les sorties :

### Acteurs :

- `actor … metadata` : `can_reproduce` demande l'âge de reproduction et, chez qui mange, une `nutrition` d'au moins 50 ; `infertile` et `max_children` (enfants vivants) n'arrêtent que qui porte : un mâle engendre si sa compagne le peut. Un `false` après un `true` ne dit pas l'infertilité : une réserve entamée suffit. Ce qui ouvre ou ferme une naissance : `wiki:Reproduction`.
- `actor … stats` rend des valeurs **déjà agrégées** — tout y est, du socle de l'espèce aux bonus de niveau (santé, mana et endurance seulement), jusqu'aux points de compétence gagnés à vivre — le niveau, lui, vient de l'expérience : n'ajoute rien par-dessus. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié tant qu'`adult_age` n'est pas atteint, seuil que `subspecies … stats` donne pour toute la lignée, avec `breeding_age`. La valeur adulte ne s'en déduit pas pour autant : la base de la lignée n'est pas celle du corps.
- `actor … surroundings` se compte comme `walked`, au pas du corps, qui ne nage que vers une autre terre : `intimate` ≤ 25 tuiles, `common` ≤ 120 ; `common_with_boat` ≤ 240 à vol d'oiseau, si son royaume a un bateau de transport ; `adrift` : dans l'eau ou sur un îlot non compté. Hors de l'intime, qui n'a ni lien, ni charge, ni meurtre, ni nom de bête se compte par cité ou par `asset_id`, sauf un pensant sans cité ou un groupe d'un seul. `life_stage` se tait à `adult`, `sapient` devant `kin`, `job` ou `role`.
- `diplomacy`, `intelligence`, `stewardship` et `warfare` (« Martial » en jeu, pas « combat ») sont des savoirs : `diplomacy` et `stewardship` ne servent qu'aux rois et aux chefs, et `damage_*` dit la force d'un coup, `warfare` compris. Le reste : `wiki:Unit_Stats`.

### Formes et mesures :

- `city … rulers` et `kingdom … rulers` donnent la succession, datée comme en jeu — le premier d'un royaume l'a fondé ; bourse du souverain en place : `population.ruler_money`.
- `geography … frozen` donne, terre par terre, la part gelée puis ses tuiles : `permafrost`, le biome gelé pour toujours ; `snow` et `ice`, la neige et la glace de la carte même ; `frost`, le gel passager.
- `houses` (cité, royaume) compte les chantiers, comme le jeu : `ground … metadata` les signale par `under_construction`.
- `kingdom … metadata` porte `ferries` quand la couronne tient une coque de transport : une seule sert tout le royaume, quelle que soit sa cité.
- `religion … metadata` : `cities` et `kingdoms` comptent qui l'a faite sienne, pas où vivent ses fidèles : une cité ne la prend que si son chef y croit, un royaume que si son roi la décrète.
- `tiles … tile_info` : `block` nomme ce qui barre la marche, que personne ne franchit à pied ; `islet`, une terre trop petite pour compter — sans elle ni `island_id`, c'est l'eau ; `snow`, `ice` et `frozen` (le gel passager) comme dans `geography … frozen`.
- `to_islands` (`distances`) donne les 5 îles les plus proches, dans l'ordre, par leur **tuile la plus proche**.
- `to_land` (`distances`) mesure le bras d'eau depuis **tout le rocher**, pas depuis la tuile.
- `to_nearest_city` (`distances`) vise le **quartier** le plus proche, pas le centre : on touche une ville par son bord. `to_capital` vise le centre de la capitale, et ne paraît qu'en cité.
- `walked` (`distances`, `to`) : la marche réelle, à côté du vol d'oiseau `tiles` — roche, lave et goo contournés, sans nage, au pas d'un corps sans adaptation : sable, marais, neige et, sous Entanglewood, arbres l'allongent. En tuiles de plaine, elle se convertit en temps comme elles ; absente sans terre qui les joigne.
- `world … metadata` : `months_until_next_age` est **déjà en mois**, 12 par an — il ne repasse pas par le `/ 5` d'un `world_time`.
- Nommer une section, c'est la vouloir en profondeur : là où `full` la résume, un champ `info` le signale, et la clé qui porte le bloc nomme la section à demander.
- Sous 4 membres, un corps ne rend ni `breakdown` ni ratio par tête (`fed_pct`, `housed_pct`, `*_per_capita`) : une seule âme y pèserait le quart ou plus.
- Un écart entre deux `snapshot` est un solde, jamais un compte d'événements : ce qui est né et ce qui s'est éteint se lisent dans `cumulative`, où chaque compteur ne fait que monter.
- Un préfixe `top_` ne tronque pas mais change de mesure : `top_drivers` ne garde que les deux extrêmes et ne somme à rien, quand la section rend le `drivers` complet, qui somme au `total`.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents — 3 pour les cités et les royaumes. Dans `world … leaders`, seul `persons` ne pèse que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers — il donne la part du ventre encore pleine, en pourcentage, donc son titulaire est celui qui en a le moins.
- Un `rank` est un rang de compétition (1, 2, 2, 4), ex æquo compris. Aucun pour un niveau 1, une seule cité, un seul royaume, ni une valeur que partage plus de la moitié du vivier.

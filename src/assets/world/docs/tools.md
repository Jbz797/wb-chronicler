# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 03/10/26 13:35</p>

Invoquer chaque outil via `python3 tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON, citée ici en abrégé : `kingdom … metadata`. Un seul bloc nommé (une section, `--to`, une tuile) sort nu, sans sa clé ; plusieurs gardent la leur. Ce que fixe un filtre (`-i`, un seul `-t`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre. Un compte à 0 et un drapeau faux se taisent : absent, il vaut 0 — `creatures_born` de `world … cumulative` compris. `sections` = liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … pairings` et `roster`, à nommer) ; le suffixe **`C<n>`** lit ce chapitre ; sans lui, le dernier.

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
| `history`         | `dead_kingdoms`, `entity`, `log`, `world`                                                                                        |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `population`, `ranks`, `relations`, `rulers`, `wars`  |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `members`, `metadata`, `population`, `ranks`, `traits`                              |
| `subspecies <id>` | `breakdown`, `leaders`, `members`, `metadata`, `population`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                   |
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `islet`, `tile_info`                                                                 |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                             |
| `world`           | `boats`, `cumulative`, `leaders`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`                                          |

## Options :

### `actor` :

- `--to <id | x,y | i<terre> | type>` : un corps, une tuile, une terre abordée au moins cher (`landing`) ou le plus proche de types et familles, par virgules (`nearest`) ; il rend son `circle`, chaque part en tuiles et en temps, `total_` dès qu'il y en a deux ; sur l'eau, `march_days` ne compte que la marche, l'eau se passant d'une traite, et `total_days` le tout ; `with_boat` le trajet par la coque de sa couronne, jamais à additionner, `widest_crossing` son plus long bras s'il passe le souffle ; vers un corps, `from_them` : le trajet de l'autre, s'il diffère ; seule sans section nommée.
- `--since C<n>` : ce qui a bougé depuis — `moved` est le trajet fait, et son temps au plus court, au pas du corps, quand `--to` ne donne qu'un gisement ; `gone` : mort ; `last_seen` sa dernière place

### `geography` :

- `--since C<n>` : ce qui a bougé, `[avant, après]`, `new` ou `gone` ; des soldes : un passage se lit dans `roster --since`
- `-i <id>` : une seule terre dans les sections rangées par terre, ou `islets` et `water` là où elles les comptent
- `-t <type>` (`positions`) : un `asset_id`, une famille (`trees`…) ou une liste à virgules, hors corps

### `history` :

- `entity <type> <id>` : les années d'une entité — `alliance`, `city`, `clan`, `culture`, `family`, `kingdom`, `language`, `religion`, `subspecies`, `war`
- `log` : `--since C<n>` depuis un chapitre, `--actor <id>` les entrées qui nomment un corps, `-t <event>` un type d'entrée (`kingdom_new`…)

### `tiles` :

- `-i <id>` : une terre par son id, mesurée comme `to_islands` sous `to_island`, même hors des 5 plus proches — celle où l'on se tient vaut 0
- `-r <n>` : rayon, de 0 à 2 — `distances` : la tuile demandée seule
- `--to <x,y>` : cap et mesures entre lieux (d'un corps : `actor`), sous `to` si une section la rejoint ; pas avec `-r`

### `world` :

- `pairings` : par espèce (un couple ignore la lignée), la 1ʳᵉ naissance possible (`birth_on` ; `pregnant` nomme les porteuses, à la date du jeu ; sinon `now` chez des amants, faute de trace) et l'écart du couple ; `barren`, par lignée, les corps qui n'enfanteront jamais ; `lovers`, choisis d'abord ; `barred`, ce qui arrête la naissance, pas la rencontre, suivi du corps en cause (`hungry`, `water`, `tiny_islet` : îlot de 5 tuiles ou moins), ou la loi WB pour le couple ; règles : `wiki:Reproduction`
- `roster` : chaque vivant, `life_stage` hors adultes ; `-t` type ou famille, `--trait <id>`, `--sapient`, `--settle` (`settle` vrai ou `child`) et `--barred`, l'inverse, `-i` une terre, `islets` ou `water` ; `--since C<n>` : les arrivés, les `was_on` et les morts (`gone`, `old_from` : la vieillesse exclue avant) ; passé 50, un compte par terre, espèce et stade

---

## Carte :

`map/show.py <x,y> [C<n>]` — cerne la tuile sur la carte du chapitre et rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**. `--zoom <n>` : les n tuiles alentour, agrandies, nord en haut — **à lire toi-même** pour la forme d'une côte, ses parts d'eau, de sol et de roche en dessous.

## Lire les sorties :

### Acteurs :

- `actor … companions` : seul `lover` fait un couple ; `best_friend` est une amitié.
- `actor … metadata` : `can_reproduce` demande l'âge de reproduction et, chez qui mange, une `nutrition` d'au moins 50 ; `infertile` et `max_children` (enfants vivants) n'arrêtent que qui porte : un mâle engendre si sa compagne le peut. `breeds_on` date l'âge qui l'ouvrira, `adult_on` la majorité ; `islet`, le centre de son îlot : s'il change, c'en est un autre. `settle`, chez un pensant : `true` s'il fonderait sur place, `child` si l'âge seul l'arrête, ou l'obstacle le plus durable, ce qu'il est avant là où il se tient (`settle_more` : les autres).
- `actor … stats` rend des valeurs **déjà agrégées**, socle, niveau (santé, mana et endurance seulement) et compétences compris : n'ajoute rien par-dessus. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié jusqu'à `adult_on`. La valeur adulte ne se lit pas sur celle de la lignée. `swim` : `breath` tant que dure le souffle, `reach` noyade comprise, sur l'endurance et la santé de l'instant, et `rested` ce qui en change reposé ; `never` pour qui brûle dans l'eau, `unlimited` pour qui n'y peine pas.
- `actor … surroundings` se compte en temps à son pas, `total_…` sur chaque ligne, terrain pesé, nageant vers une autre terre seulement ; une coque qu'il rejoint y paraît (`boat_…`), sans être un corps : `intimate` ≤ 30 min, `common` ≤ 2 h ; `common_with_boat`, hors de sa terre, ≤ 2 h en bateau, marches comprises, si son royaume a un transport ; à bord, par l'eau puis à pied ; `water` et `islet_tiles` comme dans `tiles … tile_info`, tus sur sa propre terre ou son îlot. Hors de l'intime, qui n'a ni lien, ni charge, ni meurtre, ni nom de bête se compte par cité ou par `asset_id`, sauf un pensant sans cité ou un groupe d'un seul. Seul, il donne son `nearest` à vol d'oiseau. `sapient` se tait devant `kin`, `job` ou `role`.
- `diplomacy`, `intelligence`, `stewardship` et `warfare` (« Martial » en jeu, pas « combat ») sont des savoirs : `diplomacy` et `stewardship` ne servent qu'aux rois et aux chefs, et `damage_*` dit la force d'un coup, `warfare` compris. Le reste : `wiki:Unit_Stats`.
- `happiness` (`actor … stats`) : la barre du jeu en %, 50 au neutre — heureux dès 60, malheureux sous 30.

### Entités et comptes :

- `city … rulers` et `kingdom … rulers` donnent la succession, datée comme en jeu — le premier d'un royaume l'a fondé ; bourse du souverain en place : `population.ruler_money`.
- `description` et `flavor` d'un trait disent l'ambiance, jamais l'effet : il tient dans `stats`, que `dormant` dit endormies par l'ère et `absorbed` bues par une borne, le reste dans `wiki:Creature_Traits` ou `wiki:Subspecies_Traits`. Un don se pèse contre sa lignée (`subspecies … stats`), jamais contre un autre corps.
- `history` lit l'historique de WB : `world`, ce que chaque année a vu naître, mourir ou s'éteindre, l'année en cours `so_far`, une année absente sans rien de neuf, les ~20 dernières seules ; `entity`, les états d'une entité (noms nus : `population`…) et ses gains de l'année (`births`, `deaths`, `kills`, `…_created`), l'avant de la fenêtre approché (`around_year`). Seuls les vivants y ont leurs années. De quoi meurent les siens : `deaths_by_cause`, au `metadata` d'une cité, d'un royaume, d'un clan ou d'une sous-espèce ; ceux du monde, sur `world … cumulative` ou `history world`, jamais en additionnant les lignées, les éteintes n'ayant plus de `metadata`.
- `houses` (cité, royaume) compte les chantiers, comme le jeu.
- `kingdom … metadata` : une seule coque de transport (`ferries`) sert tout le royaume.
- `religion … metadata` : `cities` et `kingdoms` comptent qui l'a faite sienne, pas où vivent ses fidèles : une cité ne la prend que si son chef y croit, un royaume que si son roi la décrète.
- `top_drivers` ne garde que les deux extrêmes et ne somme à rien ; le `drivers` de la section, complet, somme au `total`.
- `world … cumulative,snapshot --since C<n>` rend les écarts ; celui de `snapshot` est un solde, jamais un compte d'événements : ce qui est né et ce qui s'est éteint se lisent dans `cumulative`, où chaque compteur ne fait que monter.
- Sous 4 membres, une entité ne rend ni `breakdown` ni ratio par tête (`fed_pct`, `housed_pct`, `*_per_capita`).

### Lieux et trajets :

- `crow_tiles` (`to`, `distances`, `moved`) : à vol d'oiseau sur 8 directions (une diagonale compte 1,41), à citer tel quel, jamais refait à la règle ; pas un compte de pas.
- `geography … frozen` : par terre, la part gelée puis ses tuiles : `permafrost`, le biome gelé pour toujours ; `snow` et `ice`, la neige et la glace de la carte même ; `frost`, le gel passager.
- `ground` (`biomes`) : le sol sans biome ; `rock` joint monts et sommets, sa plus grande parcelle est un massif.
- `heart` (`islands`, `waters`) : le point le plus loin des rives.
- `ridges` (`geography`) : là où deux terres se touchent sans eau, une crête de roche infranchissable à pied, `at` sa tuile du milieu.
- `strait_to_land` (`distances`) : l'eau à nager (`swim_tiles`) depuis **tout le rocher**, écueils à sec gratuits ; de rive à rive, `islet … to_islands`.
- `tiles … tile_info` : `block` barre la marche ; `islet_tiles`, la taille d'un îlot, sous 300 tuiles de sol, que `islet` décrit entier, roche et îlots accolés compris ; sur l'eau, `sea`, `lake` ou `river` (leur id), sinon `pond_tiles` ; `snow`, `ice` et `frozen` comme dans `geography … frozen`.
- `to_islands` (`distances`) : les 5 îles les plus proches, à vol d'oiseau jusqu'à leur **tuile la plus proche**.
- `to_nearest_city` (`distances`) vise le **quartier** le plus proche, pas le centre. `to_capital` vise le centre de la capitale, et ne paraît qu'en cité.
- `walk_tiles` (`distances`, `to`) : les tuiles faites à pied, roche, lave et goo contournés ; sable, marais, neige et arbres sous Entanglewood n'allongent que le temps. Hors d'`actor`, rien ne se nage, au `speed` 10 : absente sans terre qui les joigne.
- `waters` : `seas` touche un bord du monde, `rivers` chaîne par les coins des eaux larges de moins de 3 tuiles, `lakes` est le reste — dès 64 tuiles ; `unlisted` compte les mares en dessous (`pond_tiles`) et écarte les détroits de plus de 1 024 tuiles.
- Un coin joint deux parcelles (`patches`), jamais deux eaux ; deux terres ou un pas, seulement dans un chunk de 16 et sans roche.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents (3 cités ou royaumes), compté sous `unranked`. Dans `world … leaders`, seul `persons` ne pèse que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers : la part du ventre encore pleine, en %, dont le titulaire a le moins.
- Un `rank` est un rang de compétition (1, 2, 2, 4), ex æquo compris. Aucun pour un niveau 1, une seule cité, un seul royaume, ni une valeur que partage plus de la moitié du vivier.

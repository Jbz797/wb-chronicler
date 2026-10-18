# 🧰 Outils du chroniqueur

<p class="metadata">Date de mise à jour : 18/10/26 18:26</p>

Chaque outil : `python tools/<nom>/info.py [arg] [sections] [C<n>]`, sortie JSON ou refus `✗` seul sur stderr, citée en abrégé : `kingdom … metadata`. Un seul bloc nommé (une section, `--to`, une tuile) sort nu ; plusieurs gardent leur clé. Ce que fixe un filtre (`-i`, un seul `-t`, `--actor`…) ne se répète pas : un champ absent y vaut le filtre. Un compte à 0 et un drapeau faux se taisent : absent, il vaut 0 — ou 1 (`gen`, `level`, `past_chiefs`), `normal` (taxe). `sections` = liste à virgules (`full` par défaut = toutes, sauf `geography`, `world … laws`, `pairings` et `roster`, à nommer) ; le suffixe **`C<n>`** lit ce chapitre ; sans lui, le dernier.

| Commande          | Sections                                                                                                                               |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `actor <id>`      | `companions`, `gear`, `inventory`, `metadata`, `plot`, `ranks_in_species`, `stats`, `surroundings`, `traits`                           |
| `alliance <id>`   | `breakdown`, `identity`, `kingdoms`, `leaders`, `metadata`, `pop`, `ranks`, `wars`                                                     |
| `boat <id>`       | `combat`, `crew`, `identity`, `inventory`, `metadata`, `traits`                                                                        |
| `book <id>`       | `gains`, `metadata`, `origin`, `teaches`                                                                                               |
| `city <id>`       | `army`, `books`, `breakdown`, `buildings`, `gear`, `identity`, `inventory`, `leaders`, `loyalty`, `metadata`, `pop`, `ranks`, `rulers` |
| `clan <id>`       | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                               |
| `culture <id>`    | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `family <id>`     | `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`                                                                         |
| `geography`       | `biomes`, `bodies`, `burning`, `entity_types`, `frozen`, `gear`, `islands`, `positions`, `ridges`, `totals`, `waters`                  |
| `ground <id>`     | `boats`, `inventory`, `metadata`, `occupants`                                                                                          |
| `history`         | `dead_kingdoms`, `entity`, `log`, `world`                                                                                              |
| `kingdom <id>`    | `boats`, `breakdown`, `cities`, `gear`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `relations`, `rulers`, `wars`               |
| `language <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `religion <id>`   | `books`, `breakdown`, `identity`, `leaders`, `metadata`, `pop`, `ranks`, `traits`                                                      |
| `subspecies <id>` | `breakdown`, `leaders`, `metadata`, `pop`, `ranks`, `species`, `stats`, `taxonomy`, `traits`                                           |
| `tiles <x,y>`     | `actors`, `context`, `distances`, `ground`, `islet`, `tile_info`                                                                       |
| `war <id>`        | `attackers`, `defenders`, `metadata`                                                                                                   |
| `world`           | `boats`, `cumulative`, `laws`, `leaders`, `metadata`, `pairings`, `plots`, `roster`, `snapshot`                                        |

## Options :

### `actor` :

- `--since C<n>` : ce qui a bougé depuis — `moved` : le trajet fait et son temps au plus court, au pas du corps ; `stats` et `traits` : l'écart entre deux instants, pas ce qui s'est passé entre ; `gone` : mort, `was_at` sa place alors ; `to.then` : ce but compté alors
- `--statuses` : `held`, ses statuts durables par chapitre, `seen` ses chapitres ; rien d'entre deux
- `--to <id | x,y | b<id> | i<terre> | type>` : un corps, une tuile, un bâtiment, une terre abordée au moins cher (`landing`) ou le plus proche de chaque type, famille ou ressource (`nearest`), par virgules pour les seuls types — deux nombres font une tuile, un corps se vise seul ; un bâtiment à sa tuile, une tâche à la sienne (`task_target`) ; son `circle`, `total_` dès deux parts ; sur l'eau, `march_days` ne compte que la marche, l'eau se passant d'une traite, et `total_days` le tout ; `with_boat` le trajet par la coque de sa couronne, jamais à additionner, `widest_crossing` son plus long bras s'il passe le souffle ; vers un corps, `from_them` : le trajet de l'autre s'il diffère ; `chunks_apart` à 0 ou 1 : tout près pour le jeu.

### `geography` :

- `--since C<n>` : ce qui a bougé, `[avant, après]`, `new` ou `gone` ; des soldes : un passage se lit dans `roster --since` — sauf `positions`, qui nomme chacun par son id
- `-i <id>` : une seule terre dans les sections rangées par terre, ou `islets` et `water` là où elles les comptent
- `-t <type>` : sous `positions`, types, familles (`trees`…) et ressources, par virgules, hors corps ; sous `biomes -i`, un biome ou un sol, ses 5 plus grandes parcelles

### `history` :

- `entity <type> <id>` : les années d'une entité, son refus liste les types
- `log` : `--since C<n>` depuis un chapitre, `--actor <id>` les entrées qui nomment un corps, `-t <event>` un type (`kingdom_new`…)

### `tiles` :

- `-i <id>` : une terre par son id, mesurée comme `to_islands` sous `to_island`, même hors des 5 plus proches — celle où l'on se tient vaut 0
- `-r <n>` : rayon, de 0 à 2 — `distances` : la tuile demandée seule
- `--to <x,y>` : cap et mesures entre lieux (d'un corps : `actor`), sous `to` si une section la rejoint ; pas avec `-r`

### `world` :

- `laws` : les lois par leur libellé du jeu, celui de `wiki:World_Laws`
- `pairings` : par espèce (un couple ignore la lignée), la 1ʳᵉ naissance possible (`birth_on` ; `pregnant` nomme les porteuses, à la date du jeu ; sinon `now` chez des amants, faute de trace) et l'écart du couple ; `pair` : la porteuse d'abord, dont l'enfant prend la cité, sinon celle de l'autre (`drawn` : tirée au sort) ; `barren`, par lignée, les corps qui n'enfanteront jamais ; `missing: meal`, des spores sans estomac, que seul un repas lâche ; `lovers`, choisis d'abord ; `barred`, ce qui arrête la naissance, pas la rencontre, et le corps en cause (`hungry`, `water` : à flot, `tiny_islet` : îlot de 5 tuiles au plus), ou la loi WB ; règles : `wiki:Reproduction`
- `roster` : chaque vivant, `life_stage` hors adultes ; `-t` type ou famille, `--trait`, `--has <compte>`/`--top <mesure>`, `--status`/`--task <id>`, `--sapient`, `--settle` (`settle` vrai ou `child`) et `--barred`, l'inverse, `-i` une terre, `islets` ou `water`, `--patch <x,y>` sa parcelle, `--<entité> <id>` (`--city`, `--clan`…) ses membres ; `--since C<n>` : `arrived`, `moved` (`was_on`) et `gone` (`old_from` : la vieillesse exclue avant) — d'une entité, `arrived` y entre, `left` en sort vivant ; sous `--has`, les seuls comptes changés, `[avant, après]`

---

## Carte :

`map/show.py <x,y> [C<n>]` — cerne la tuile sur la carte du chapitre, rend le chemin de l'image ; **à toi de l'ouvrir pour le joueur**. `--zoom <n>` : les n tuiles autour — **à lire toi-même** pour la forme d'une côte —, leurs parts d'eau, de sol et de roche en dessous.

## Lire les sorties :

### Acteurs :

- `actor … companions` : seul `lover` fait un couple, `best_friend` non.
- `actor … metadata` : `can_reproduce` demande l'âge de reproduction et, chez qui mange, une `nutrition` ≥ 50 ; `infertile` et `max_children` (enfants vivants ; tus avec `children`, lignée stérile) n'arrêtent que qui porte : un mâle engendre si sa compagne le peut. `breeds_on` date l'âge qui l'ouvrira, `adult_on` la majorité, `hatches_as` ce qu'un œuf sera éclos, selon elle, `statuses_left` le reste d'un statut qui dure : `soon` sous 3 mois, `months` sous 1 an, sinon `years` ; `islet` : le centre de son îlot, autre s'il change. `settle`, chez un pensant : `true` s'il fonderait sur place, `child` si l'âge seul l'arrête, ou l'obstacle le plus durable, ce qu'il est avant là où il se tient (`settle_more` : les autres).
- `actor … stats` rend des valeurs **déjà agrégées**, socle, niveau (santé, mana et endurance seulement) et compétences compris : n'y ajoute rien. Celles d'un mineur sont **bridées** : `damage_max` et `health_max` valent la moitié jusqu'à `adult_on`. La valeur adulte ne se lit pas sur celle de la lignée. `swim` : `breath` tant que dure le souffle, `reach` noyade comprise, sur l'endurance et la santé de l'instant, et `rested` ce qui en change reposé ; `never` pour qui brûle dans l'eau, `unlimited` pour qui n'y peine pas.
- `actor … surroundings` se compte à son pas, `total_…` par ligne, terrain pesé ; comme `--to`, ne nage que si son but est sur une autre terre ; une coque qu'il rejoint y paraît (`boat_…`), sans être un corps : `intimate` ≤ 30 min, `common` ≤ 2 h ; `common_with_boat`, hors de sa terre, ≤ 2 h en bateau, marches comprises, si son royaume a un transport ; à bord, par l'eau puis à pied ; `water` et `islet_tiles` comme dans `tiles … tile_info`, tus sur sa terre ou son îlot. Hors de l'intime, qui n'a ni lien, ni charge, ni meurtre, ni nom de bête se compte par cité ou par `asset_id`, sauf un pensant sans cité ou un groupe d'un seul. Seul, il donne son `nearest` à vol d'oiseau. `sapient` se tait devant `kin`, `job` ou `role`.
- `diplomacy`, `intelligence`, `stewardship` et `warfare` (« Martial » en jeu, pas « combat ») sont des savoirs : `wiki:Unit_Stats`.
- `gen` (`actor … metadata`) : absent, le corps a paru sans parents ; dès 2, ils sont `parent` sous `surroundings`.
- `happiness` (`actor … stats`) : la barre du jeu en %, seuils `wiki:Happiness`.
- `in_building` : sous ce toit ; `at_building` : à une tuile au plus.
- `task` : une suite d'actions, sans son étape ; il ne dort que si `statuses` dit `sleeping` (`wiki:Behaviour_Tasks`).

### Entités et comptes :

- `buildings`, `houses` et `buildings_built` comptent un chantier dès sa pose, que `born` date ; nommée, `city … buildings` les liste, chantier marqué : ce qu'elle tait, la cité ne l'a pas.
- `creatures_created` (`cumulative`) : ce qui paraît sans naître — semé, migrant, invoqué, changé d'espèce, coque —, jamais une naissance (`creatures_born`).
- `description` et `flavor` d'un trait sont l'ambiance ; son effet tient dans `stats`, que `dormant` dit endormies par l'ère et `absorbed` bues par une borne, le reste dans `wiki:Creature_Traits` ou `wiki:Subspecies_Traits`. Un don se pèse contre sa lignée (`subspecies … stats`), jamais contre un autre corps.
- `gap_tiles` (`kingdom … relations`) : de bord à bord des quartiers, à vol d'oiseau, tu s'ils se touchent.
- `ground … metadata` : `cost`, pris à la réserve dès la pose (`wiki:Buildings`) ; `health` ne sort que blessé, près de `health_max` ; un arbre tombe d'un coup (`wiki:Wood`).
- `history` (WB) : `world`, ce que chaque année a vu naître, mourir ou s'éteindre — WB la clôt à l'entrée de son 12ᵉ mois, d'où `until`, et `since` sur celle en cours (`so_far`) —, une année absente : rien de neuf, les ~20 dernières seules ; `entity`, ses états (noms nus : `pop`…) et ses gains de l'année (`births`, `deaths`, `kills`, `…_created`), l'avant de la fenêtre approché (`around_year`). Seuls les vivants y ont leurs années. De quoi meurt le monde : `world … cumulative` ou `history world`, jamais la somme des `deaths_by_cause` des lignées, les éteintes n'en ayant plus. `unknown` : ce que le jeu ne range nulle part (fièvre des Cendres…)
- `kingdom … metadata` : une seule coque (`ferries`) sert tout le royaume.
- `migrants` (`city … metadata`) : ce qui retient la loi d'en amener, sinon `soon` ou `later` (`wiki:World_Laws`).
- `religion … metadata` : `cities` et `kingdoms` comptent qui l'a faite sienne, pas où vivent ses fidèles : `wiki:Religions`.
- `report` parle par images : « No fire, no warmth » dit le bois qui manque, pas le feu.
- `rulers` (cité, royaume) : la succession, datée comme en jeu — le premier d'un royaume l'a fondé ; bourse du souverain : `pop.ruler_money`.
- `top_drivers` ne garde que les deux extrêmes et ne somme à rien ; `drivers`, complet, somme au `total` ; chaque terme, par son id : `wiki:Loyalty`.
- `world … cumulative,snapshot --since C<n>` rend les écarts ; celui de `snapshot` est un solde, jamais un compte d'événements : naissances et extinctions se lisent dans `cumulative`, qui ne fait que monter ; `gone_without_death` : les corps partis sans mort comptée (`deaths_without_body`, l'inverse).
- Sous 4 membres, une entité ne rend ni `breakdown` ni ratio par tête (`fed_pct`, `housed_pct`, `*_per_capita`).

### Lieux et trajets :

- `crow_tiles` (`to`, `distances`, `moved`) : à vol d'oiseau sur 8 directions (une diagonale compte 1,41), à citer tel quel, jamais refait à la règle ; pas un compte de pas.
- `geography … frozen` : par terre, la part gelée puis ses tuiles : `permafrost`, le biome gelé en toute saison ; `snow` et `ice`, la neige et la glace de la carte même ; `frost`, le gel passager.
- `ground` (`biomes`) : le sol sans biome ; `rock` joint monts et sommets, sa plus grande parcelle est un massif.
- `heart` (`islands`, `waters`) : le point le plus loin des rives.
- `ridges` (`geography`) : là où deux terres se touchent sans eau, une crête de roche infranchissable, `at` sa tuile du milieu.
- `strait_to_land` (`distances`) : l'eau à nager (`swim_tiles`) depuis **tout le rocher**, écueils à sec gratuits ; de rive à rive, `islet … to_islands`.
- `tiles … tile_info` : `block` barre la marche ; `islet_tiles`, la taille d'un îlot, sous 300 tuiles de sol, que `islet` décrit entier, roche et îlots accolés compris ; sur l'eau, `sea`, `lake` ou `river` (leur id), sinon `pond_tiles` ; `snow`, `ice` et `frozen` comme dans `geography … frozen`.
- `to_islands` (`distances`) : les 5 plus proches, à vol d'oiseau jusqu'à leur **tuile la plus proche**.
- `to_nearest_city` (`distances`) : la plus proche par son `edge`, un quartier. `to_capital` vise le centre de la capitale.
- `walk_tiles` (`distances`, `to`) : les tuiles faites à pied, roche, lave et goo contournés ; sable, marais, neige et arbres sous Entanglewood n'allongent que le temps. Hors d'`actor`, rien ne se nage, au `speed` 10 : absente sans terre qui les joigne.
- `waters` : `seas` touche un bord du monde, `rivers` chaîne par les coins des eaux larges de moins de 3 tuiles, `lakes` est le reste — dès 64 tuiles ; `unlisted` compte les mares en dessous (`pond_tiles`) et écarte les détroits de plus de 1 024 tuiles.
- Un coin joint deux parcelles (`patches`), jamais deux eaux ; deux terres ou un pas, seulement dans un chunk de 16 et sans roche.

### Classements :

Toute section `leaders` nomme la première place, ex æquo compris : personne quand plus de 3 la partagent ou qu'ils passent la moitié du vivier, ni dans un groupe de moins de 4 concurrents (3 cités ou royaumes), compté sous `unranked`. Dans `world … leaders`, seul `persons` ne pèse que les êtres pensants.

- Chaque titulaire porte sa `value`, un `score` excepté : ses points grimpent avec le nombre de rivaux. Seul `hungriest` se lit à l'envers : le ventre le moins plein, en %.
- Un `rank` est un rang de compétition (1, 2, 2, 4), ex æquo compris. Aucun pour un niveau 1, une seule cité, un seul royaume, ni une valeur que partage plus de la moitié du vivier.

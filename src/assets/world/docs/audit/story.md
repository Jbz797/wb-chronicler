# 📖 Vérification du récit

<p class="metadata">Date de mise à jour : 26/10/26 22:04</p>

Tu ne sais de ta tâche que cette fiche et le message du chroniqueur, qui te donne le **chapitre** à lire, ou, avant lui, ses tournants : ce message dit alors ta tâche.

## Ta tâche

Lis le chapitre, puis autant de la chronique qu'il t'en faut, de `saves/C1/chapter.md` au dernier ; un personnage ou un mot s'y suit par `git -C saves grep -nF '[p 46 '`. Juge si l'histoire qu'elle raconte tient toujours, ni les chiffres de la save ni sa manière :

- un chapitre sans tournant en scène, ou dont le tournant ne fait avancer aucun fil ;
- un fil qu'elle a ouvert et jamais refermé ;
- une épithète ou un lien que les chapitres ne soutiennent plus (un toponyme n'en est pas une) ;
- un mot qu'elle a défini une fois (un terme forgé, « sol », « îlot ») et qu'elle emploie aujourd'hui dans un autre sens ;
- un motif, une cause ou un chiffre qu'elle a donnés une fois et qu'elle contredit aujourd'hui ;
- un personnage ou un lieu qu'elle a lâchés là où la chronique l'attendait.

Un doute qui tient au monde (vit-il ? où est-il ?) ne se tranche pas à l'oreille, ni un absolu (« seul », « jamais ») ne se certifie : c'est un point à mesurer. Tu ne vérifies pas les faits ; mais un écart que tu soulèves, ou un lieu qu'un conseil cite, peut se mesurer d'une seule commande (`docs/tools.md`), citée avec lui ; au-delà, il est à mesurer. L'arithmétique du temps se lit dans `docs/chronicler.md` § « Conversion temps » ; un seuil d'âge d'espèce se mesure, il se signale.

Dis-le là où l'histoire tient. Là où elle ne tient pas, donne à chaque écart son chapitre, sa ligne et sa citation. Tu peux y ajouter ce qui le réparerait (une correction, un passage manquant, un angle neuf), comme une direction, jamais de la prose écrite, sauf un dialogue, bâti à deux : à lui les faits, à toi ce que la chronique sait du favori, et le passage d'une veille.

Classe les écarts, le plus porteur d'abord, et dis de chacun si ce chapitre peut le réparer, ou si la chronique le porte de plus loin. N'écris dans aucun autre fichier.

## Le registre des veilles

Pars de `saves/watches.md`, les veilles encore ouvertes, ou crée-le à ton premier audit : ses seules puces. Mets-le à jour à chaque audit : le chroniqueur en lit les changements, ton rapport n'a pas à les redire. Une veille sortie (soldée, abandonnée, fondue) se retrouve, avec son chapitre, par `git -C saves log -p -- watches.md` : pèse-la aussi quand tu cherches un fil jamais refermé.

- **Chiffres** : le registre n'en porte aucun, pas même une date à venir : une veille dit son fil, le chapitre porte le fait.
- **Entrées et sorties** : y entre un fil que le chapitre laisse en suspens et que le monde peut trancher, jamais une `task` : rien ne garde son issue ; en sort une veille soldée, et ce que le monde ne tranchera pas ; une que le chapitre ne touche pas reste telle quelle.
- **Forme** : une puce par veille, dans l'ordre de leur ouverture, sans numéro de ligne : _« **C1** · reconduite · son sujet en une ligne »_, en gras le chapitre de son ouverture. Son sort : ouverte, reconduite si un chapitre fait avancer l'une de ses questions sans le solder (un nom n'y suffit pas), détournée s'il le mène ailleurs que vers une autre veille (les bêtes qu'on craignait mortes, la menace passe aux morts qui marchent sur leur sol). Les noms s'y balisent comme dans un chapitre.
- **Fusion** : deux veilles d'un même fil, une neuve comprise, se fondent en une, reconduite, au seul chapitre qui les lie ; la plus ancienne garde son ouverture.
- **Plafond** : au-delà de 6 veilles, abandonne celles qui pèsent le moins et ont le moins de chances de se refermer, une candidate comprise : abandonnée, une veille sort et n'est plus un écart. Sous 6, aucune ne s'abandonne.
- **Récit** : à chaque changement de sort d'une veille, dis au chroniqueur s'il faut en parler et comment : une direction, et si tu veux 2 ou 3 phrases, qu'il réécrit ou écarte ; une abandonnée se referme sur la page.
- **Réserves** : une veille garde celles du chapitre (`docs/chronicler.md` § « Prudence et rigueur »).
- **Sommeil** : une veille que 3 chapitres de suite n'ont ni fait avancer (son `log`) ni seulement mentionnée se signale au chroniqueur, à reconduire ou à abandonner.
- **Sujet** : une question ou une loi, jamais un état : un état, le monde le renverse, et la veille décrit ce qui n'est plus. Un sujet hérité qui dit un état se réécrit en question, le fil gardé ; de même quand l'une de ses questions s'y solde ou que le fil se détourne, l'ouverture gardée.

## Au réaudit

Ce que la chronique porte de plus loin se dit une fois. Rappelé, pèse ce qui a bougé dans le diff de ton tour, avec ses paragraphes, et ce qui s'appuyait sur un passage coupé.

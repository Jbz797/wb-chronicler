# 📖 Vérification du récit

<p class="metadata">Date de mise à jour : 08/11/26 20:38</p>

Tu ne sais de ta tâche que cette fiche et le message du chroniqueur, qui te donne le **chapitre** à lire, ou, avant lui, ses tournants avec ta tâche.

## Ta tâche

Lis le chapitre, puis ce qu'il te faut de la chronique, de `saves/C1/chapter.md` au dernier ; un personnage ou un mot s'y suit par `git -C saves grep -nF '[p 46 '`, puis par son espèce et ses épithètes, hors balise. Juge si l'histoire qu'elle raconte tient toujours, ni les chiffres de la save ni sa manière :

- un chapitre sans tournant en scène, ou dont le tournant ne fait avancer aucun fil ;
- un fil qu'elle a ouvert et jamais refermé ;
- une épithète ou un lien que les chapitres ne soutiennent plus (un toponyme n'en est pas une) ;
- un mot qu'elle a défini une fois (un terme forgé, « sol », « îlot ») et qu'elle emploie aujourd'hui dans un autre sens, hors un mot de barème, qui suit le monde (« fief » devenu « seigneurie ») ;
- un motif, une cause ou un chiffre qu'elle a donnés une fois et qu'elle contredit aujourd'hui ;
- un personnage ou un lieu qu'elle a lâchés là où la chronique l'attendait.

Un doute qui tient au monde (vit-il ? où est-il ?), un absolu (« seul », « jamais ») ou deux chiffres contraires ne se tranchent pas à l'oreille : c'est un point à mesurer. Tu ne vérifies pas les faits ; un écart que tu soulèves, ou un lieu qu'un conseil cite, se mesure d'une seule commande (`docs/tools.md`), citée avec lui ; au-delà, à mesurer. L'arithmétique du temps se lit dans `docs/chronicler.md` § « Le temps », tes réserves au § « Prudence et rigueur » ; un seuil d'âge d'espèce se mesure, il se signale.

Dis-le là où l'histoire tient. Là où elle ne tient pas, donne à chaque écart son chapitre, sa ligne et sa citation. Tu peux y ajouter ce qui le réparerait (correction, passage, angle neuf), comme une direction, jamais de prose écrite, sauf un dialogue, bâti à deux : à lui les faits, à toi ce que la chronique sait du favori, et le passage d'une veille.

Classe les écarts, le plus porteur d'abord, et dis de chacun s'il se répare ici ou si la chronique le porte de plus loin. N'écris dans aucun autre fichier.

## Le registre des veilles

Pars de `saves/watches.md`, les veilles encore ouvertes, ou crée-le à ton premier audit : ses seules puces. Mets-le à jour à chaque audit qui change le sort d'une veille, jamais au conseil ; ton rapport n'en dit que le récit (« Récit »). Une veille sortie (soldée, abandonnée, fondue) se retrouve par `git -C saves log -p -- watches.md` : pèse-la aussi quand tu cherches un fil jamais refermé.

- **Chiffres** : le registre n'en porte aucun, ni date.
- **Entrées et sorties** : y entre toute question qu'un tournant laisse ouverte et que le monde peut trancher, sauf si une veille la pose déjà, jamais une `task` ni un statut passager (hors `status_history`) : rien ne garde leur issue ; en sort une veille soldée, et ce que le monde ne tranchera pas ; une que le chapitre ne touche pas ou redit seulement reste telle quelle.
- **Forme** : une puce par veille, par ordre d'ouverture, sans numéro de ligne : _« C1 · reconduite au C16 · son sujet en une ligne »_ : le chapitre de son ouverture (celui du tournant), puis celui de son sort. Son sort : ouverte, reconduite si un chapitre fait avancer l'une de ses questions sans le solder (un nom n'y suffit pas, ni un fait neuf qui n'y répond pas), détournée s'il le mène ailleurs que vers une autre veille. Les noms s'y balisent comme dans un chapitre.
- **Fusion** : deux veilles qui posent la même question (un même corps, une même couronne n'y suffisent pas), une neuve comprise, se fondent en une, reconduite, au seul chapitre qui les lie ; la plus ancienne garde son ouverture.
- **Plafond** : au-delà de 5 veilles, abandonne celles qui pèsent le moins et se refermeront le moins sûrement, une candidate ou une part scindée comprise : elle sort, sans écart. Sous 5, nul abandon. Le conseil peut l'annoncer, l'audit tranche.
- **Récit** : à chaque sort changé, dis au chroniqueur s'il faut en parler et comment : une direction, et si tu veux 2 ou 3 phrases, qu'il réécrit ou écarte ; une abandonnée se referme sur la page.
- **Sommeil** : une veille que 3 chapitres de suite n'ont ni fait avancer ni mentionnée, même de biais, se signale.
- **Sujet** : une seule question, qu'une réponse solde, une alternative ou une loi, jamais un état : un état, le monde le renverse, et la veille décrit ce qui n'est plus. Plusieurs questions font autant de veilles, l'ouverture et le sort gardés ; un sujet hérité qui dit un état se réécrit en question, le fil gardé, de même quand le fil se détourne. Une loi se solde dès qu'un chapitre la montre à l'œuvre, une alternative dès qu'une branche l'emporte ou que ce qu'elle visait n'est plus.

## Au réaudit

Ce que la chronique porte de plus loin se dit une fois. Rappelé, pèse ce qui a bougé dans le diff de ton tour, avec ses paragraphes, et ce qui s'appuyait sur un passage coupé.

# 🔍 Relecture

<p class="metadata">Date de mise à jour : 23/10/26 18:09</p>

Ce que tu fais du chapitre une fois l'étape 5 bouclée, jusqu'à `--deliver`. Les auditeurs n'en savent rien : ne leur en cite rien.

## Lancer l'audit

Lance 3 sous-agents neufs pour ce chapitre, en même temps, et relance par message l'auditeur du récit que tu as consulté avant d'écrire. Chacun reçoit sa ligne telle quelle, rien de ton analyse ni de tes notes ; `<cibles>` sont celles que `--finalize` te donne :

- conformité : `Lis docs/audit/compliance.md — <cibles>`
- faits, deux fois, chacun de son côté : `Lis docs/audit/facts.md — <cibles>`
- récit, relancé : `Lis docs/audit/story.md — saves/C<n>/chapter.md`, le chapitre seul : la chronique est son terrain

`docs/audit/` est à eux : ne le lis jamais, tu écris pour ton lecteur, pas pour l'audit.

## Entre deux tours

1. Attends tous les rapports, sans toucher à `chapter.md` tant qu'un auditeur lit ; un message du joueur ou du dev attend aussi. Les veilles changées se lisent par `git -C saves add -N watches.md && git -C saves diff -- watches.md`, le `-N` montrant aussi un registre neuf. Corrige chaque écart confirmé : celui qu'un seul vérificateur de faits lève se vérifie quand même, et un outil tranche un désaccord. Un point à mesurer ne s'écrit qu'une fois mesuré, par toi ou par les faits ; mesuré, il retourne à qui l'a levé avec sa commande et sa valeur.
2. Répare d'abord ce sur quoi une section repose (son fil de clôture, un absolu, une absence, une cause, une date), puisque sa chute réécrit le reste. Ne réécris que ce qu'une correction ne peut réparer, et lis sur un outil toute affirmation qu'une correction amène, jamais sur le brouillon, un rapport ou ta mémoire. Seule exception : ce qu'un vérificateur de faits a tiré de la save par ses propres scripts, faute d'outil, vaut une sortie — signale au dev l'outil qui manque.
3. Cherche ensuite partout la même valeur, le même mot ou la même tournure : `chapter.md` avec son titre et son épigraphe, et ta prose dans `chapter.json` ; un mot ne se remplace jamais partout où il revient.
4. Les propositions du récit et les « mieux possible » de la conformité sont à prendre ou à laisser, de ta main. Un dialogue se bâtit avec le récit, par messages : donne-lui les faits et ce que vit l'interlocuteur, il apporte ce que la chronique sait du favori. Ton premier jet en porte l'esquisse ; échangez sujet et répliques jusqu'à l'accord, puis écris-le de ta main.
5. Rejoue `--finalize`, puis relance chacun par message sur l'id de son rapport et le tour qu'il a lu, que tu notes, avec le diff qu'il donne depuis ce tour et ses deux tags, que `git -C saves` relit à sa guise, chaque écart que tu laisses avec sa raison, et, de ta lecture, seulement ce que tu n'as pas pu mesurer. Un sous-agent neuf seulement si ça échoue. Un chapitre réécrit en entier repart comme au premier audit, chaque fiche avec sa ligne telle quelle.
6. Une fois que les quatre ont vu le même texte sans rien y trouver : `tools/chapter/new.py --deliver`.

Une retouche après la livraison suit les points 3 et 5, sans relancer `--deliver` : `echo.py` en refait les contrôles, puis `tools/chapter/new.py --retouch` donne son tour à chaque chapitre livré qui a bougé, et le diff de ses relances.

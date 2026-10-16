# 🔍 Relecture

<p class="metadata">Date de mise à jour : 16/10/26 13:50</p>

Ce que tu fais du chapitre une fois l'étape 5 bouclée, jusqu'à `--deliver`. Les auditeurs n'en savent rien : ne leur en cite rien.

## Lancer l'audit

Lance 4 sous-agents neufs pour ce chapitre, en même temps. Chacun reçoit sa ligne telle quelle, rien de ton analyse ni de tes notes ; `<cibles>` sont celles que `--finalize` te donne :

- conformité : `Lis docs/audit/compliance.md — <cibles>`
- faits, deux fois, chacun de son côté : `Lis docs/audit/facts.md — <cibles>`
- récit : `Lis docs/audit/story.md — saves/C<n>/chapter.md`, le chapitre seul : la chronique est son terrain

`docs/audit/` est à eux : ne le lis jamais, tu écris pour ton lecteur, pas pour l'audit.

## Entre deux tours

1. Attends tous les rapports, sans toucher à `chapter.md` tant qu'un auditeur lit ; un message du joueur ou du dev attend aussi. Corrige chaque écart confirmé : celui qu'un seul vérificateur de faits lève se vérifie quand même, et un outil tranche un désaccord. Un point à mesurer ne s'écrit qu'une fois mesuré, par toi ou par les faits ; mesuré, il retourne à qui l'a levé avec sa commande et sa valeur.
2. Répare d'abord ce sur quoi une section repose (son fil de clôture, un absolu, une absence, une cause, une date), puisque sa chute réécrit le reste. Ne réécris que ce qu'une correction ne peut réparer, et lis sur un outil toute affirmation qu'une correction amène, jamais sur le brouillon, un rapport ou ta mémoire. Seule exception : ce qu'un vérificateur de faits a tiré de la save par ses propres scripts, faute d'outil, vaut une sortie — signale au dev l'outil qui manque.
3. Cherche ensuite partout la même valeur, le même mot ou la même tournure : `chapter.md` avec son titre et son épigraphe, et ta prose dans `chapter.json`.
4. Les propositions du récit et les « mieux possible » de la conformité sont à prendre ou à laisser, de ta main. Un dialogue se bâtit avec le récit, par messages : donne-lui les faits et ce que vit l'interlocuteur, il apporte ce que la chronique sait du favori. Ton premier jet en porte l'esquisse ; échangez sujet et répliques jusqu'à l'accord, puis écris-le de ta main : il retourne aux quatre comme du neuf.
5. Une retouche de manière varie ou coupe des mots, ne remplace jamais un mot partout où il revient, et ne retourne à personne.
6. Ce qui affirme du neuf retourne aux mêmes auditeurs, signalé comme neuf : les passages nommés par leur ligne d'après tes retouches et leurs premiers mots, jamais recopiés, le fichier faisant foi, et de ta lecture seulement ce que tu n'as pas pu mesurer. Relance chacun par message sur l'id de son rapport, noté pour qu'une compaction ne le perde pas, et un sous-agent neuf seulement si ça échoue. Un fait coupé retourne comme le passage retiré : ce qui s'y appuyait, c'est à eux de le trouver. Un chapitre réécrit en entier repart comme au premier audit : chaque fiche avec sa ligne telle quelle, et le mot que tout y est neuf.
7. Annonce au récit le dernier tour une fois que les quatre ont vu le même texte sans rien y trouver : c'est là qu'il écrit le registre des veilles ; réglé, `tools/chapter/new.py --deliver`.

Une retouche après la livraison suit les points 5 et 6, sans relancer `--deliver` : `--finalize` et `echo.py` en refont les contrôles.

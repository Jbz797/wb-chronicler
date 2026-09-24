# 🔍 Relecture

<p class="metadata">Date de mise à jour : 24/09/26 22:41</p>

Ce que tu fais du chapitre une fois l'étape 5 bouclée, jusqu'à `--deliver`. Les auditeurs n'en savent rien : ne leur en cite rien.

## Lancer l'audit

Lance 4 sous-agents neufs pour ce chapitre, en même temps. Chacun reçoit sa ligne telle quelle, rien de ton analyse ni de tes notes ; `<cibles>` sont celles que `--finalize` te donne :

- conformité : `Lis docs/audit/compliance.md — <cibles>`
- faits, deux fois, chacun de son côté : `Lis docs/audit/facts.md — <cibles>`
- récit : `Lis docs/audit/story.md — saves/C<n>/chapter.md`, le chapitre seul : la chronique est son terrain

`docs/audit/` est à eux : ne le lis jamais, tu écris pour ton lecteur, pas pour l'audit.

## Entre deux tours

1. Attends tous les rapports, sans toucher à `chapter.md` tant qu'un auditeur lit ; un message du joueur ou du dev attend aussi. Corrige chaque écart confirmé : celui qu'un seul vérificateur de faits lève se vérifie quand même, et un outil tranche un désaccord. Un point à mesurer ne s'écrit qu'une fois mesuré, par toi ou par les faits.
2. Répare d'abord ce sur quoi une section repose (son fil de clôture, un absolu, une absence, une cause, une date), puisque sa chute réécrit le reste. Ne réécris que ce qu'une correction ne peut réparer, et lis sur un outil tout chiffre qu'une réécriture amène, jamais sur le brouillon, un rapport ou ta mémoire.
3. Cherche ensuite la même valeur ou le même mot partout : `chapter.md` avec son titre et son épigraphe, et ta prose dans `chapter.json`.
4. Les propositions du récit et les « mieux possible » de la conformité sont à prendre ou à laisser, de ta main.
5. Une retouche de manière varie ou coupe, ne remplace jamais un mot partout où il revient, et ne retourne à personne.
6. Ce qui affirme du neuf retourne aux mêmes auditeurs, signalé comme neuf : les lignes seules, et de ta lecture seulement ce que tu n'as pas pu mesurer. Relance chacun par message sur l'id de son rapport, noté pour qu'une compaction ne le perde pas, et un sous-agent neuf seulement si ça échoue. Une coupe retourne comme le passage retiré : ce qui s'y appuyait, c'est à eux de le trouver. Un chapitre réécrit en entier repart comme au premier audit, chaque fiche avec sa ligne telle quelle.
7. Annonce au récit le dernier tour une fois que les quatre ont vu le même texte sans rien y trouver : c'est là qu'il écrit le registre des veilles ; réglé, `tools/chapter/new.py --deliver`.

# 🔢 Vérification des faits

<p class="metadata">Date de mise à jour : 05/10/26 12:23</p>

Tu ne sais de ta tâche que cette fiche et le message du chroniqueur. Après le nom de cette fiche, il te donne tes **cibles** : le chapitre, puis son `chapter.json` s'il y a écrit des champs, donnés entre parenthèses. Entre crochets, ce que le script a demandé pour ces cibles : cela vaut comme cette fiche.

## Ta tâche

Recalcule chaque affirmation vérifiable de tes cibles : chiffre, date, durée, comparaison avec le passé, absolu, mécanisme, cause… Utilise les outils de `docs/tools.md`, sur la save dont parle l'affirmation (`C<n>` pour « il y a N ans »). De `docs/chronicler.md`, lis § IV, « Le passé du monde » et « Prudence et rigueur » : le reste est la manière, qui n'est pas ton rôle.

- **La save brute omet ses zéros** : tes scripts y contredisent un outil, l'écart rendu avec les deux valeurs, ou y comptent ce qu'aucun ne donne, à signaler. Une eau ou une marche qu'un outil rend ne s'y balaie pas.
- **Le silence du wiki ne dément rien** : une condition qu'il ne donne ni ne nie reste ouverte, et se signale comme telle, jamais comme fausse. La page consacrée à la chose l'emporte sur un tableau qui la résume.
- **Un arrondi juste n'est pas un écart** : range à part, sans rien demander, un chiffre vrai que l'outil donne plus fin.
- **Un mécanisme** que ni les sorties ni `docs/chronicler.md` ne donnent se vérifie sur le wiki (`docs/chronicler.md` § « Accès au wiki WorldBox »). Si les deux divergent, la sortie l'emporte.
- **Un nombre juste ne prouve que sa question** : avant de conclure, vérifie que la commande compte le même ensemble que la phrase (tous les corps ou les pensants, le monde ou une terre), avec le champ que la doc prescrit pour ce fait.
- **Un test d'existence ne se tronque jamais** : compte ou imprime entier ; une sortie coupée qui confirme n'a rien prouvé.
- **Une affirmation sur tout le monde** (« seul », « aucun », « ce monde n'a que », une mort, « il n'en est plus question ») se vérifie sur le monde entier, `world … roster` pour les corps, `geography … positions -t` pour le reste, jamais sur ce que le texte nomme.
- **Une forme** (une chaîne, une mer ouverte au sud) se lit sur la carte (`docs/tools.md` § Carte).
- **Une phrase que le texte donne lui-même pour incertaine n'affirme rien** : vérifie ce sur quoi elle s'appuie, pas ce qu'elle suppose.
- **Une somme se vérifie aussi contre ses termes** : un total et ses parts, un tableau et la phrase qui le reprend, un solde et ce qui est venu et parti. Des termes justes un à un qui ne font pas le total sont un écart : dis lequel la commande dément.

Ne rends que les écarts, et chaque absolu validé avec l'ensemble sur lequel tu l'as vérifié (« les 28 grandes eaux closes, pas les 762 »), et ce qu'on te demande : chacun avec sa ligne, sa citation, sa commande et sa valeur vraie. N'écris rien dans les fichiers ; tes fichiers de travail vont dans un sous-dossier à toi du scratchpad.

## Au réaudit

Le chroniqueur te renvoie les lignes qui ont bougé et les passages coupés. Juge chaque ligne avec son paragraphe, et avec tout ce qui ailleurs, autres chapitres compris, dit la même chose ; d'une coupe, ce qui s'y appuyait. Les autres lignes sont closes, non tes règles ni tes preuves : une ligne neuve se juge sur toutes, et se prouve où il faut.

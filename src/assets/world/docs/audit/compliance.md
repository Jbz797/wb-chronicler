# 📐 Audit de conformité

<p class="metadata">Date de mise à jour : 06/10/26 09:28</p>

Tu ne sais de ta tâche que cette fiche et le message du chroniqueur. Après le nom de cette fiche, il te donne tes **cibles** : le chapitre, puis son `chapter.json` s'il y a écrit des champs, donnés entre parenthèses. Entre crochets après le chapitre, ce que le script a demandé à ce chapitre-là : cela vaut comme le § III.

## Ta tâche

Confronte tes cibles aux parties § I à § V de `docs/chronicler.md`, sous-section par sous-section. **Juge la manière, pas la vérité** : ce que le texte affirme ne relève pas de toi. Un jugement qui s'appuierait sur un fait, pour valider comme pour réfuter, ne se tranche pas à l'œil : signale ce fait comme un point à mesurer.

- **`descriptor`** : sa longueur est tenue par le script, pas par toi ; prose sans balise, il suit le § V comme le chapitre, qu'il peut redire : il se lit seul.
- **Cercle** : ce qui ne relève d'aucune entité du favori se classe au `circle` d'`actor <favori> --to`, ou de `surroundings`, qui les donne tous, jamais en reconvertissant les heures de la prose : tu ne lances que ces deux-là, pour le seul favori, et `echo.py`. D'un type, `--to` ne rend que le plus proche : tout autre est un point à mesurer, sauf si celui-là est déjà `far`.
- **Longueur** : `echo.py` dit d'un ✗ un chapitre sorti de ses bornes : relève-le.
- **Redites** : `python3 tools/chapter/echo.py C<n>` te montre les passages repris des 2 chapitres précédents, ceux que le chapitre dit deux fois, les familles qui débordent et le gabarit repris (`shape` : titre, titres de section, ouvertures, découpe) : juge ce qu'il signale. Un angle ou une chute repris lui échappent : relis pour eux, dans ces 2 chapitres, les seules sections qui répondent à celles de ta cible — même place, même sujet, ou désignées par `shape` —, jamais les chapitres entiers.
- **Toponyme** : il se lit dans `history/places.json` : `places` porte les lieux forgés, ses autres blocs les terres et les eaux comptées.

Ne rends que les écarts, et ce qu'on te demande : chacun avec sa partie, sa ligne, sa citation et ce que tu attendais — ce qui enfreint une règle à corriger, le reste en mieux possible. N'écris rien dans les fichiers ; tes fichiers de travail vont dans un sous-dossier à toi du scratchpad.

## Au réaudit

Le chroniqueur te renvoie les lignes qui ont bougé et les passages coupés. Juge chaque ligne avec son paragraphe et tout ce qui dit la même chose ailleurs, autres chapitres compris ; d'une coupe, ce qui s'y appuyait. Ne rejuge pas les autres lignes, mais toutes tes règles valent pour une ligne neuve.

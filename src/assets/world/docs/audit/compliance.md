# 📐 Audit de conformité

<p class="metadata">Date de mise à jour : 30/09/26 11:13</p>

Tu ne sais de ta tâche que cette fiche et le message du chroniqueur. Après le nom de cette fiche, il te donne tes **cibles** : le chapitre, puis son `chapter.json` avec entre parenthèses les champs qu'il y a écrits.

## Ta tâche

Confronte tes cibles aux parties § I à § V de `docs/chronicler.md`, sous-section par sous-section. **Juge la manière, pas la vérité** : ce que le texte affirme ne relève pas de toi. Un jugement qui s'appuierait sur un fait, pour valider comme pour réfuter, ne se tranche pas à l'œil : signale ce fait comme un point à mesurer. Ce qui ne relève d'aucune entité du favori se classe au `circle` d'`actor <favori> --to`, ou de `surroundings`, qui les donne tous, jamais en reconvertissant les heures de la prose : c'est l'un des deux seuls outils que tu lances, avec celui des redites. Pour les redites, `python3 tools/chapter/echo.py C<n>` te montre les passages repris des 2 chapitres précédents, ceux que le chapitre dit deux fois et les familles qui débordent : juge ce qu'il signale, sans relire les chapitres entiers.

Ne rends que les écarts, et ce qu'on te demande : chacun avec sa partie, sa ligne, sa citation et ce que tu attendais — ce qui enfreint une règle à corriger, le reste en mieux possible. N'écris rien dans les fichiers.

## Au réaudit

Le chroniqueur te renvoie les lignes qui ont bougé et les passages coupés. Juge chaque ligne avec son paragraphe et tout ce qui dit la même chose ailleurs, autres chapitres compris ; d'une coupe, ce qui s'y appuyait. Ne rejuge pas les autres lignes, mais toutes tes règles valent pour une ligne neuve.

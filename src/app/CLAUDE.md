## Arborescence

- Un composant vit là où il est **appelé**, en transitif : il n'est transverse que si l'un de ses usagers l'est, sinon il descend avec lui
- Un `index.ts` regroupe ce que plusieurs dossiers consomment ; un sous-composant privé à son parent s'importe par chemin direct

## Commentaires

- Pas de commentaires au-dessus des `constructor`, hooks `ng*` et méthodes `init`
- Pas de commentaires dans `app.component.ts`

## ESLint

- `max-lines` est configuré avec `skipBlankLines: true` et `skipComments: true`
- Vérifier les erreurs avec `yarn lint:fix && yarn build`

## i18n

- Beaucoup de clés sont consommées via template literal (ex: `species_${assetId}`, `role_${role}`). Toujours grep le préfixe avant de supprimer une clé.
- Les libellés que WorldBox connaît viennent de ses propres locales (`locales/<lang>/` dans `resources.assets`) ; le reste est du vocabulaire chroniqueur, traduit à la main.
- `fr.json` et `en.json` portent les mêmes clés, triées ; un genre s'écrit `<base>_f` / `<base>_m`, la clé nue servant de repli aux langues qui ne fléchissent pas.

## Méthodes

- Convertir les méthodes courtes (une seule instruction) en arrow function properties quand c'est possible (< 165 chars)
- Hooks `ng*` : aucun modificateur de visibilité

## Readonly

`readonly` uniquement sur les fields `private`. Le linter forcera ailleurs si nécessaire (signals créés in-place).

## UI

Utiliser au maximum les composants ng-zorro (https://ng.ant.design/components/overview/en) plutôt que du HTML/CSS custom

## Visibilité

Priorité : **`private` > `protected` > `public`**. Toujours utiliser le plus restrictif possible (TypeScript force à relâcher si nécessaire).

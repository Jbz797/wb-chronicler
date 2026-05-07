## Commentaires

- Pas de commentaires au-dessus des `constructor`, hooks `ng*` et méthodes `init`
- Pas de commentaires dans `app.component.ts`
- Un commentaire `//` au-dessus de chaque méthode multi-ligne, aucun au-dessus des one-line

## Décorateurs

- `@Pipe` sur une seule ligne : `@Pipe({ name: 'xxx', standalone: true })`
- `pure: true` est le défaut Angular, ne pas l'écrire explicitement

## ESLint

- `max-lines` est configuré avec `skipBlankLines: true` et `skipComments: true`
- Vérifier les erreurs avec `yarn lint && yarn build`

## Méthodes

- Convertir les méthodes courtes (une seule instruction) en arrow function properties quand c'est possible (< 165 chars)
- Hooks `ng*` sans `public`

## UI

Utiliser au maximum les composants ng-zorro (https://ng.ant.design/components/overview/en) plutôt que du HTML/CSS custom

import angularStrict from 'eslint-config-angular-strict';

export default [
  ...angularStrict,
  {
    files: ['**/*.mjs', '**/*.js'],
    languageOptions: {
      globals: { // Named one by one rather than pulled from `globals`, which reaches this project only as a transitive dependency.
        clearTimeout: 'readonly', console: 'readonly', process: 'readonly', setTimeout: 'readonly',
      },
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module' }, // the preset pins this one to 2018, which predates `??`, and the inner setting wins
    },
    rules: {
      '@stylistic/lines-between-class-members': 'off', // a run of one-line fields reads as one block
      '@stylistic/max-len': ['error', { code: 165, tabWidth: 2 }], // the project's own measure
      'import-x/no-extraneous-dependencies': ['error', { devDependencies: true }], // dev tooling reaches for dev dependencies
      'import-x/order': 'off', // `perfectionist` orders them, as on the `.ts` side
      'max-classes-per-file': 'off', // a dev service is one file, and its parts have nowhere else to live
      'no-console': 'off', // a dev-only service reports to its terminal
      'unicorn/consistent-class-member-order': 'off', // it wants `#private` first, `perfectionist` wants it last — and `perfectionist` governs the `.ts` side
      'unicorn/prefer-temporal': 'off', // `Temporal` is not shipping yet
    },
  },
  {
    files: ['**/*.ts'],
    rules: {
      /* */
    },
  },
];

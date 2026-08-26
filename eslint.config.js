import angularStrict from 'eslint-config-angular-strict';

export default [
  ...angularStrict,
  {
    files: ['**/*.mjs', '**/*.js'],
    languageOptions: {
      globals: { clearTimeout: 'readonly', console: 'readonly', setTimeout: 'readonly' }, // named rather than pulled from `globals`, a transitive package
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module' }, // the preset pins this one to 2018, which predates `??`, and the inner setting wins
    },
    rules: {
      '@stylistic/max-len': ['error', { code: 165, tabWidth: 2 }], // the project's own measure
      'import-x/no-extraneous-dependencies': ['error', { devDependencies: true }], // dev tooling reaches for dev dependencies
      'import-x/order': 'off', // `perfectionist` orders them, as on the `.ts` side
      'no-console': 'off', // a dev-only service reports to its terminal
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

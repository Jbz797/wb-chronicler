import angularStrict from 'eslint-config-angular-strict';

export default [
  ...angularStrict,
  {
    files: ['mods/*/mod.json'],
    rules: { 'unicorn/filename-case': 'off', 'unicorn/name-replacements': 'off' }, // names the mod loader and the C# projects impose
  },
  {
    files: ['**/*.mjs', '**/*.js'],
    languageOptions: {
      globals: { // Named one by one rather than pulled from `globals`, which reaches this project only as a transitive dependency.
        clearTimeout: 'readonly', console: 'readonly', process: 'readonly', setTimeout: 'readonly',
      },
    },
    rules: {
      'import-x/no-extraneous-dependencies': ['error', { devDependencies: true }], // dev tooling reaches for dev dependencies
      'max-classes-per-file': 'off', // a dev service is one file, and its parts have nowhere else to live
      'no-console': 'off', // a dev-only service reports to its terminal
    },
  },
  {
    files: ['src/assets/world/docs/chronicler.md'],
    rules: { 'markdown/no-multiple-h1': 'off' }, // each part of the chronicler's guide opens on its own H1
  },
];

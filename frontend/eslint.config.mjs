import { dirname } from 'path';
import { fileURLToPath } from 'url';
import { FlatCompat } from '@eslint/eslintrc';

const __filename = fileURLToPath(import.meta.url);
const __dirname  = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

const eslintConfig = [
  ...compat.extends('next/core-web-vitals', 'next/typescript'),
  {
    rules: {
      /* Accessibilité */
      'jsx-a11y/alt-text':          'warn',
      'jsx-a11y/aria-props':        'warn',
      'jsx-a11y/aria-proptypes':    'warn',
      'jsx-a11y/aria-unsupported-elements': 'warn',
      'jsx-a11y/role-has-required-aria-props': 'warn',
      /* React */
      'react/no-unescaped-entities': 'off',
      '@next/next/no-html-link-for-pages': 'off',
      /* TypeScript */
      '@typescript-eslint/no-explicit-any':   'warn',
      '@typescript-eslint/no-unused-vars':    ['warn', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/prefer-nullish-coalescing': 'off',
      /* Imports */
      'import/no-duplicates': 'error',
    },
  },
];

export default eslintConfig;

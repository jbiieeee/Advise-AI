/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './core/templates/**/*.html',
    './core/static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Example of an OKLCH color using a CSS variable
        brand: 'oklch(var(--color-brand) / <alpha-value>)',
      }
    },
  },
  plugins: [],
}

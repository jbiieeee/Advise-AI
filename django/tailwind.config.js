/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './core/templates/**/*.html',
    './core/static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        navy: '#0F172A',
        'light-blue': '#38BDF8',
        white: '#FFFFFF',
        'light-gray': '#F1F5F9',
        brand: '#0F172A', // fallback to navy
      }
    },
  },
  plugins: [],
}

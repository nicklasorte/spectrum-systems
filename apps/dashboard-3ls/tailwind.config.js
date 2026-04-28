/** @type {import('tailwindcss').Config} */
module.exports = {
  // D3L-MASTER-01 Phase 7 — class-strategy dark mode. The `dark` class is
  // applied to <html> by ThemeProvider. Status colors (red/orange/yellow/
  // green/gray) keep their semantic meaning across both themes.
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

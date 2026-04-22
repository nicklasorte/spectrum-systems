/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        status: {
          good: '#10b981',
          warning: '#f59e0b',
          critical: '#ef4444',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
};

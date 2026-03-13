/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'gene-blue': '#4C9BE8',
        'gene-dark': '#0f1117',
        'gene-panel': '#1a1d27',
        'gene-border': '#2a2d3a',
      },
    },
  },
  plugins: [],
}

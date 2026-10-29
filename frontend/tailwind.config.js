/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        vedic: {
          50: '#fffbf5',
          100: '#fef5ea',
          200: '#fce6cb',
          300: '#f9d2a2',
          400: '#f4ab59',
          500: '#ef8a25',
          600: '#e06f17',
          700: '#ba5314',
          800: '#944217',
          900: '#783816',
          950: '#411c09',
        },
        saffron: {
          50: '#fff9eb',
          100: '#ffefc6',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
        },
        parchment: {
          50: '#faf8f2',
          100: '#f4ede0',
          200: '#ebdcc5',
          300: '#decaa5',
          400: '#d1b483',
          500: '#c5a067',
        }
      },
      fontFamily: {
        devanagari: ['"Noto Sans Devanagari"', 'Mangal', '"Nirmala UI"', 'sans-serif'],
        traditional: ['"Rozha One"', '"Noto Serif Devanagari"', 'serif'],
        manuscript: ['"Martel"', '"Noto Serif Devanagari"', 'serif'],
        sans: ['Inter', '"Noto Sans Devanagari"', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}

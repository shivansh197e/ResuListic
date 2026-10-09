/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'Poppins', 'sans-serif'],
        nunito: ['Nunito', 'sans-serif'],
        poppins: ['Poppins', 'sans-serif'],
      },
      colors: {
        pastel: {
          blue: '#e0f2fe',       // Soft blue / sky-100
          blueLight: '#f0f9ff',  // sky-50
          blueDark: '#0284c7',   // sky-600
          mint: '#dcfce7',       // Soft mint / emerald-100
          mintLight: '#f0fdf4',  // emerald-50
          mintDark: '#059669',   // emerald-600
          lavender: '#f3e8ff',   // Soft purple / purple-100
          rose: '#ffe4e6',       // Soft pink / rose-100
          amber: '#fef3c7',      // Soft warm amber / amber-100
          card: '#ffffff',       // Crisp white card
          surface: '#f8fafc',    // Soft background / slate-50
          muted: '#64748b',      // Accessible slate text / slate-500
          dark: '#1e293b',       // High contrast readable text / slate-800
        },
      },
      boxShadow: {
        'soft': '0 4px 20px -2px rgba(148, 163, 184, 0.12)',
        'soft-md': '0 8px 25px -4px rgba(148, 163, 184, 0.16)',
        'soft-lg': '0 12px 35px -5px rgba(148, 163, 184, 0.18)',
        'inner-soft': 'inset 0 2px 4px 0 rgba(148, 163, 184, 0.06)',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.25rem',
        '3xl': '1.75rem',
        'full': '9999px',
      },
    },
  },
  plugins: [],
};

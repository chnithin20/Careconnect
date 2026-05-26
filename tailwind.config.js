/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scan all templates and JS for used classes
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  corePlugins: {
    // Keep preflight off — our custom CSS handles base styles
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        primary:        '#3b82f6',
        'primary-dark': '#2563eb',
        secondary:      '#ec4899',
        accent:         '#8b5cf6',
        danger:         '#ef4444',
        success:        '#10b981',
        muted:          '#94a3b8',
        bg:             '#000c24',
      },
      fontFamily: {
        inter:  ['Inter', 'sans-serif'],
        outfit: ['Outfit', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

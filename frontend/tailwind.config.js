/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme from existing dashboard
        bg: "#05080d",
        bgAlt: "#080c14",
        surface: "#0b1120",
        surfaceHi: "#0f1a2e",
        border: "#152035",
        borderHi: "#1e3050",
        amber: "#e8a020",
        amberDim: "#5a3d08",
        green: "#2dcc7a",
        greenDim: "#0d4a2a",
        blue: "#3a9fd8",
        blueDim: "#0d2e50",
        red: "#d95f5f",
        teal: "#2abfbf",
        tealDim: "#0a3a3a",
        purple: "#8b67d4",
        text: "#b8c8dc",
        textDim: "#445a78",
        textFaint: "#1e2e45",
        white: "#e8f0f8",
      },
    },
  },
  plugins: [],
}

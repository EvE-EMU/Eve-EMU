/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        eve: {
          bg: "#0a0f14",
          panel: "#0c1218",
          edge: "#1c2a36",
          cyan: "#4db8d8",
          gold: "#b8922a",
        },
      },
      fontFamily: {
        eve: ['"Segoe UI"', "system-ui", "sans-serif"],
        mono: ['"Consolas"', '"Courier New"', "monospace"],
      },
      fontSize: {
        micro: ["10px", { lineHeight: "1.3" }],
        ui: ["13px", { lineHeight: "1.35" }],
      },
    },
  },
  plugins: [],
};

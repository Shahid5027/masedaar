import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#081226",
          900: "#0f1e3a",
          800: "#172a4f",
          700: "#223b6b",
        },
        risk: {
          low: "#15803d",
          lowBg: "#dcfce7",
          medium: "#b45309",
          mediumBg: "#fef3c7",
          high: "#b91c1c",
          highBg: "#fee2e2",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;


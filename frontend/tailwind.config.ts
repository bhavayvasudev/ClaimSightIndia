import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        lavender: "#918df6",
        iris: "#9580ff",
        mint: "#33c758",
        "mint-wash": "#def6e4",
        amber: "#ffa600",
        sky: "#2c78fc",
        magenta: "#d6409f",
        ember: "#ff3e00",
        carbon: "#181925",
        graphite: "#666666",
        ash: "#999999",
        fog: "#e8e8e8",
        mist: "#f5f5f5",
        linen: "#fafafa",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      maxWidth: {
        content: "1200px",
        copy: "620px",
      },
      borderRadius: {
        card: "16px",
        input: "8px",
        table: "24px",
      },
      boxShadow: {
        subtle: "rgba(0,0,0,0.08) 0px 1px 1px 1px, rgba(0,0,0,0.06) 0px 0px 0px 0.5px",
        "subtle-2": "rgba(0,0,0,0.08) 0px 1px 1px 0px, rgba(0,0,0,0.05) 0px 0px 0px 1px",
        panel:
          "rgba(0,0,0,0.06) 0px 1px 3px 0px, rgba(0,0,0,0.06) 0px 8px 16px 0px, rgba(0,0,0,0.02) 0px 0px 0px 1px",
      },
      letterSpacing: {
        display: "-0.045em",
        heading: "-0.02em",
        body: "-0.02em",
      },
    },
  },
  plugins: [],
};

export default config;

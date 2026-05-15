import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // Navy brand from gtm-engine. brand-600 (#0f1f4e) is the canonical
        // "primary" everywhere — the lighter and darker steps are derived to
        // give us hover/active states without leaving the palette.
        brand: {
          50:  "#f3f5fa",
          100: "#e8ecf4",
          200: "#c6d0e2",
          300: "#9faecc",
          400: "#5a72a3",
          500: "#1a2d6b",
          600: "#0f1f4e",
          700: "#0a1535",
          800: "#070f24",
          900: "#040818",
        },
        ink: {
          50:  "#fafafa",
          100: "#f5f5f5",
          200: "#e5e5e5",
          300: "#d4d4d4",
          400: "#a3a3a3",
          500: "#737373",
          600: "#525252",
          700: "#404040",
          800: "#262626",
          900: "#171717",
          950: "#0a0a0a",
        },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(15,31,78,0.04), 0 4px 12px rgba(15,31,78,0.04)",
        pop:  "0 1px 2px rgba(15,31,78,0.10), 0 8px 24px rgba(15,31,78,0.14)",
        ring: "0 0 0 4px rgba(15,31,78,0.18)",
      },
      borderRadius: {
        lg: "0.625rem",
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      keyframes: {
        "fade-in":   { "0%": { opacity: "0", transform: "translateY(4px)" },  "100%": { opacity: "1", transform: "translateY(0)" } },
        "scale-in":  { "0%": { opacity: "0", transform: "scale(0.96)" },     "100%": { opacity: "1", transform: "scale(1)" } },
        "shimmer":   { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
      },
      animation: {
        "fade-in":  "fade-in 200ms ease-out",
        "scale-in": "scale-in 180ms ease-out",
        "shimmer":  "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;

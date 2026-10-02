/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Semantic tokens only: every surface/text color resolves through the
        // theme variables in index.css so light and dark stay readable.
        background: "var(--bg-primary)",
        surface: "var(--bg-surface)",
        elevated: "var(--bg-elevated)",
        soft: "var(--bg-soft)",
        deep: "var(--bg-deep)",
        hover: "var(--bg-hover)",
        "hover-strong": "var(--bg-hover-strong)",
        // CSS tuples are comma-separated; do not mix them with slash syntax.
        "surface-border": "rgba(var(--border-rgb), <alpha-value>)",
        ink: "var(--text-primary)",
        muted: "var(--text-muted)",
        accent: "rgba(var(--accent-rgb), <alpha-value>)",
        gain: "rgba(var(--gain-rgb), <alpha-value>)",
        loss: "rgba(var(--loss-rgb), <alpha-value>)",
        warn: "rgba(var(--warn-rgb), <alpha-value>)",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      }
    },
  },
  plugins: [],
}

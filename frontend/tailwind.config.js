/** @type {import('tailwindcss').Config} */
// Design tokens (DESIGN.md) mapped to CSS variables (see index.css) so a single set
// of utility classes themes correctly in both light and dark. Names match the design
// markup (on-surface, outline-variant, primary-fixed-dim, bg-0/1/2, …) so views port
// nearly verbatim. Channels are space-separated RGB → Tailwind /opacity modifiers work.
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-0": v("--bg-0"),
        "bg-1": v("--bg-1"),
        "bg-2": v("--bg-2"),
        "on-surface": v("--text"),
        "on-surface-variant": v("--text-muted"),
        outline: v("--outline"),
        "outline-variant": v("--outline-variant"),
        "surface-container-low": v("--surface-container-low"),
        "surface-container": v("--bg-1"),
        "surface-container-high": v("--bg-2"),
        "surface-container-highest": v("--surface-container-highest"),
        primary: v("--primary"),
        "primary-fixed-dim": v("--primary"),
        "on-primary": v("--on-primary"),
        // financial semantics (stable across themes)
        positive: "#10B981",
        negative: "#EF4444",
        warning: "#F59E0B",
        info: "#64748B",
        serious: "#EF4444",
        moderate: "#F59E0B",
        "no-effect": "#94A3B8",
      },
      spacing: {
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        gutter: "16px",
        "margin-desktop": "24px",
        "margin-mobile": "16px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        "headline-lg": ["Inter"],
        "headline-lg-mobile": ["Inter"],
        "section-header": ["Inter"],
        "card-title": ["Inter"],
        "body-md": ["Inter"],
        "body-sm": ["Inter"],
        "data-table": ["Inter"],
        "label-caps": ["Inter"],
        caption: ["Inter"],
      },
      fontSize: {
        "headline-lg": ["32px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "600" }],
        "headline-lg-mobile": ["24px", { lineHeight: "1.2", fontWeight: "600" }],
        "section-header": ["18px", { lineHeight: "1.4", fontWeight: "600" }],
        "card-title": ["14px", { lineHeight: "1.4", letterSpacing: "0.05em", fontWeight: "600" }],
        "body-md": ["14px", { lineHeight: "1.6", fontWeight: "400" }],
        "body-sm": ["13px", { lineHeight: "1.5", fontWeight: "400" }],
        "data-table": ["13px", { lineHeight: "1.2", fontWeight: "500" }],
        "label-caps": ["11px", { lineHeight: "1", letterSpacing: "0.08em", fontWeight: "700" }],
        caption: ["12px", { lineHeight: "1.4", fontWeight: "400" }],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
      },
      keyframes: {
        blink: { "50%": { opacity: "0" } },
      },
      animation: {
        blink: "blink 1s step-end infinite",
      },
    },
  },
  plugins: [],
};

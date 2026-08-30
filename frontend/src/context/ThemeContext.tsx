import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

export type Theme = "dark" | "light";

export interface ThemeColors {
  background: string;
  surface: string;
  surfaceBorder: string;
  gridLines: string;
  bullish: string;
  bearish: string;
  text: string;
  textMuted: string;
  accent: string;
}

export const THEME_PALETTES: Record<Theme, ThemeColors> = {
  dark: {
    background: "#0b0e14",
    surface: "#0d121c",
    surfaceBorder: "#1e293b",
    gridLines: "#1e293b",
    bullish: "#10b981",
    bearish: "#f43f5e",
    text: "#f8fafc",
    textMuted: "#94a3b8",
    accent: "#38bdf8",
  },
  light: {
    background: "#f8fafc",
    surface: "#ffffff",
    surfaceBorder: "#e2e8f0",
    gridLines: "#e2e8f0",
    bullish: "#059669",
    bearish: "#e11d48",
    text: "#0f172a",
    textMuted: "#64748b",
    accent: "#0284c7",
  },
};

export function getChartTheme(theme: Theme) {
  const palette = THEME_PALETTES[theme];
  return {
    layout: {
      background: { color: palette.background },
      textColor: palette.text,
    },
    grid: {
      vertLines: { color: palette.gridLines },
      horzLines: { color: palette.gridLines },
    },
    candlestick: {
      upColor: palette.bullish,
      downColor: palette.bearish,
      borderUpColor: palette.bullish,
      borderDownColor: palette.bearish,
      wickUpColor: palette.bullish,
      wickDownColor: palette.bearish,
    },
    palette,
  };
}

interface ThemeContextType {
  theme: Theme;
  colors: ThemeColors;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  getChartTheme: () => ReturnType<typeof getChartTheme>;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("kuantra_theme") as Theme;
      if (saved === "light" || saved === "dark") return saved;
    }
    return "dark";
  });

  const applyDomTokens = useCallback((activeTheme: Theme) => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    const palette = THEME_PALETTES[activeTheme];

    root.style.setProperty("--bg-primary", palette.background);
    root.style.setProperty("--bg-surface", palette.surface);
    root.style.setProperty("--border-color", palette.surfaceBorder);
    root.style.setProperty("--grid-lines", palette.gridLines);
    root.style.setProperty("--color-gain", palette.bullish);
    root.style.setProperty("--color-loss", palette.bearish);
    root.style.setProperty("--text-primary", palette.text);
    root.style.setProperty("--text-muted", palette.textMuted);
    root.style.setProperty("--color-accent", palette.accent);

    if (activeTheme === "light") {
      root.classList.add("light-theme");
      root.classList.remove("dark-theme");
    } else {
      root.classList.add("dark-theme");
      root.classList.remove("light-theme");
    }
  }, []);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    if (typeof window !== "undefined") {
      localStorage.setItem("kuantra_theme", newTheme);
    }
    applyDomTokens(newTheme);

    // Sync with backend asynchronously
    fetch("http://127.0.0.1:8000/api/v1/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_theme: newTheme }),
    }).catch(() => {});
  }, [applyDomTokens]);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  // Initial load sync from backend if available
  useEffect(() => {
    applyDomTokens(theme);

    fetch("http://127.0.0.1:8000/api/v1/settings")
      .then((res) => res.json())
      .then((data) => {
        if (data && (data.active_theme === "light" || data.active_theme === "dark")) {
          if (data.active_theme !== theme) {
            setThemeState(data.active_theme);
            applyDomTokens(data.active_theme);
            if (typeof window !== "undefined") {
              localStorage.setItem("kuantra_theme", data.active_theme);
            }
          }
        }
      })
      .catch(() => {});
  }, [applyDomTokens]);

  const value = {
    theme,
    colors: THEME_PALETTES[theme],
    setTheme,
    toggleTheme,
    getChartTheme: () => getChartTheme(theme),
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
};
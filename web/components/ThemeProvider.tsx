"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type Theme = "dark" | "purple" | "rose" | "green" | "blue" | "amber" | "chronocoder" | "light" | "stone" | "sky" | "sage";

const THEMES: { value: Theme; label: string; color: string; isLight?: boolean }[] = [
  { value: "dark",         label: "Dark",        color: "#27272a" },
  { value: "purple",       label: "Purple",       color: "#a78bfa" },
  { value: "rose",         label: "Rose",         color: "#fb7185" },
  { value: "green",        label: "Green",        color: "#34d399" },
  { value: "blue",         label: "Blue",         color: "#60a5fa" },
  { value: "amber",        label: "Amber",        color: "#fbbf24" },
  { value: "chronocoder",  label: "ChronoCoder",  color: "#78283c" },
  { value: "light",        label: "Light",        color: "#e4e4e7", isLight: true },
  { value: "stone",  label: "Stone",  color: "#c4a882", isLight: true },
  { value: "sky",    label: "Sky",    color: "#7eb8e8", isLight: true },
  { value: "sage",   label: "Sage",   color: "#86b086", isLight: true },
];

const ThemeContext = createContext<{
  theme: Theme;
  setTheme: (t: Theme) => void;
  themes: typeof THEMES;
  isLight: boolean;
}>({ theme: "dark", setTheme: () => {}, themes: THEMES, isLight: false });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    const stored = localStorage.getItem("cc-theme") as Theme | null;
    if (stored) applyTheme(stored);
  }, []);

  function applyTheme(t: Theme) {
    setThemeState(t);
    localStorage.setItem("cc-theme", t);
    document.documentElement.setAttribute("data-theme", t);
    if (THEMES.find(th => th.value === t)?.isLight) {
      document.documentElement.classList.remove("dark");
    } else {
      document.documentElement.classList.add("dark");
    }
  }

  const isLight = THEMES.find(th => th.value === theme)?.isLight ?? false;

  return (
    <ThemeContext.Provider value={{ theme, setTheme: applyTheme, themes: THEMES, isLight }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

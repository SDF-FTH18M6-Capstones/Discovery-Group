import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const KEY = "stockpilot.theme";
const ThemeContext = createContext(null);

const systemPrefersDark = () =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-color-scheme: dark)").matches;

function readSaved() {
  try {
    return localStorage.getItem(KEY) || "system";
  } catch {
    return "system";
  }
}

export function ThemeProvider({ children }) {
  const [choice, setChoice] = useState(readSaved);
  const [systemDark, setSystemDark] = useState(systemPrefersDark);
  const dark = choice === "dark" || (choice === "system" && systemDark);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event) => setSystemDark(event.matches);
    query.addEventListener?.("change", onChange);
    return () => query.removeEventListener?.("change", onChange);
  }, []);

  const choose = useCallback((value) => {
    setChoice(value);
    try {
      localStorage.setItem(KEY, value);
    } catch {
  }
  }, []);

  const toggle = useCallback(() => choose(dark ? "light" : "dark"), [choose, dark]);

  const value = useMemo(() => ({ choice, dark, choose, toggle }), [choice, dark, choose, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext) || { choice: "light", dark: false, choose() {}, toggle() {} };
}

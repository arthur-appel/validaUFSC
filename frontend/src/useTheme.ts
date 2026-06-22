import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "valida-ufsc-theme";

function resolverInicial(): Theme {
  const salvo = localStorage.getItem(STORAGE_KEY);
  if (salvo === "light" || salvo === "dark") return salvo;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function aplicar(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/** Tema claro/escuro persistido em localStorage; respeita a preferência do SO na 1ª visita. */
export function useTheme(): { theme: Theme; alternar: () => void } {
  const [theme, setTheme] = useState<Theme>(resolverInicial);

  useEffect(() => {
    aplicar(theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return { theme, alternar: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

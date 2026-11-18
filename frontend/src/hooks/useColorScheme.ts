import { useEffect, useState } from "react";

const darkSchemeQuery = "(prefers-color-scheme: dark)";

export function useColorScheme(): "dark" | "light" {
  const [prefersDark, setPrefersDark] = useState(() => window.matchMedia(darkSchemeQuery).matches);

  useEffect(() => {
    const mediaQuery = window.matchMedia(darkSchemeQuery);
    const updateScheme = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
    mediaQuery.addEventListener("change", updateScheme);
    return () => mediaQuery.removeEventListener("change", updateScheme);
  }, []);

  return prefersDark ? "dark" : "light";
}

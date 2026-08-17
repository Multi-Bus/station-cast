import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "stationcast.favorites";

function read(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    // Private-mode / disabled storage: favorites just stay in-memory.
    return [];
  }
}

/** Favorites persist locally, per the design handoff's State Management table. */
export function useFavorites(initial: string[]) {
  const [favorites, setFavorites] = useState<string[]>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === null ? initial : read();
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
    } catch {
      // ignore
    }
  }, [favorites]);

  const toggle = useCallback((id: string) => {
    setFavorites((prev) => (prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]));
  }, []);

  return { favorites, toggle };
}

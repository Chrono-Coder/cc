"use client";

import { useEffect, useState } from "react";

/**
 * Debounce a value by the given delay.
 *
 * Usage:
 *   const [query, setQuery] = useState("");
 *   const debouncedQuery = useDebounce(query, 250);
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

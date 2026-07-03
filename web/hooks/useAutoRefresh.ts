"use client";

import { useCallback, useEffect, useRef } from "react";
import { useEvents } from "@/hooks/useEvents";

/**
 * Fetch data on mount and auto-refresh when an SSE event fires.
 *
 * Usage:
 *   const refresh = useAutoRefresh(fetchData, "env.switched");
 *   const refresh = useAutoRefresh(fetchData, "*");  // any event
 */
export function useAutoRefresh(
  fetcher: () => Promise<void>,
  event: string = "*",
) {
  const { subscribe } = useEvents();
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refresh = useCallback(() => fetcherRef.current(), []);

  useEffect(() => {
    refresh();
    return subscribe(event, () => refresh());
  }, [refresh, subscribe, event]);

  return refresh;
}

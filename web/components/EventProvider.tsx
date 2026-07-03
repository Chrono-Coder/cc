"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

interface SSEEvent {
  type: string;
}

type Callback = (event: SSEEvent) => void;

interface EventContextValue {
  subscribe: (type: string, cb: Callback) => () => void;
}

const EventContext = createContext<EventContextValue>({
  subscribe: () => () => {},
});

export function EventProvider({ children }: { children: ReactNode }) {
  const subscribersRef = useRef<Map<string, Set<Callback>>>(new Map());

  const subscribe = useCallback((type: string, cb: Callback) => {
    const map = subscribersRef.current;
    if (!map.has(type)) map.set(type, new Set());
    map.get(type)!.add(cb);
    return () => {
      map.get(type)?.delete(cb);
    };
  }, []);

  useEffect(() => {
    const es = new EventSource("/api/events");

    es.onmessage = (e) => {
      try {
        const event: SSEEvent = JSON.parse(e.data);
        const map = subscribersRef.current;

        // Dispatch to type-specific subscribers
        map.get(event.type)?.forEach((cb) => cb(event));

        // Dispatch to wildcard subscribers
        map.get("*")?.forEach((cb) => cb(event));
      } catch {
        // ignore malformed events
      }
    };

    return () => es.close();
  }, []);

  return (
    <EventContext.Provider value={{ subscribe }}>
      {children}
    </EventContext.Provider>
  );
}

export function useEvents() {
  return useContext(EventContext);
}

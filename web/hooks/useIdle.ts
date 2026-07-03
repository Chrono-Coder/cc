"use client";

import { useEffect, useState } from "react";

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "wheel"] as const;

/**
 * Idle after `timeoutMs` without user activity. Two deliberate behaviors:
 * - Time away from the tab COUNTS as idle — there is no visibility reset,
 *   so coming back from another app shows the idle screen instead of
 *   silently clearing it.
 * - Once idle, only a click (mousedown/touchstart) wakes; mousemove or a
 *   stray key never dismisses the screen.
 */
export function useIdle(timeoutMs: number) {
  const [idle, setIdle] = useState(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;

    function arm() {
      clearTimeout(timer);
      timer = setTimeout(() => setIdle(true), timeoutMs);
    }

    function onActivity(e: Event) {
      if (idle) {
        // wake on click only
        if (e.type === "mousedown" || e.type === "touchstart") {
          setIdle(false);
          arm();
        }
        return;
      }
      arm();
    }

    arm();
    for (const evt of ACTIVITY_EVENTS) {
      window.addEventListener(evt, onActivity, { passive: true });
    }

    return () => {
      clearTimeout(timer);
      for (const evt of ACTIVITY_EVENTS) {
        window.removeEventListener(evt, onActivity);
      }
    };
  }, [timeoutMs, idle]);

  return idle;
}

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Preview is a desktop, deliberate-intent affordance. Skip it when the pointer is coarse (touch,
 * where "hover" fires on tap and would fight navigation) or the user asked for reduced motion.
 * When `matchMedia` is unavailable (tests, old runtimes) we allow it — the caller still gates on
 * whether media exists.
 */
function prefersNoPreview(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return (
    window.matchMedia("(pointer: coarse)").matches ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export interface HoverPreview {
  /** True once the pointer has dwelled long enough to start the preview. */
  active: boolean;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
  onPointerCancel: () => void;
}

/**
 * Netflix-style dwell-to-preview: flips `active` on after `delayMs` of sustained hover, and off the
 * instant the pointer leaves. The delay stops previews from firing as the pointer sweeps across a
 * rail of cards.
 */
export function useHoverPreview(delayMs = 550): HoverPreview {
  const [active, setActive] = useState(false);
  const timer = useRef<number | null>(null);

  const clear = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const onPointerEnter = useCallback(() => {
    if (prefersNoPreview()) {
      return;
    }
    clear();
    timer.current = window.setTimeout(() => setActive(true), delayMs);
  }, [clear, delayMs]);

  const stop = useCallback(() => {
    clear();
    setActive(false);
  }, [clear]);

  // Drop any pending timer if the card unmounts mid-dwell.
  useEffect(() => clear, [clear]);

  return { active, onPointerEnter, onPointerLeave: stop, onPointerCancel: stop };
}

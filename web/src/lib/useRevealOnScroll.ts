import { type RefObject, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./useReducedMotion";

export interface RevealResult<T extends HTMLElement> {
  ref: RefObject<T>;
  /** True once the element has entered the viewport — and it never goes back to false. */
  revealed: boolean;
}

/**
 * Reveal a section once, the first time it scrolls into view.
 *
 * Deliberately one-way: re-animating on every scroll past is the thing that makes "scroll
 * animation" feel cheap, and it fights a user who is scanning up and down a long library. The
 * observer disconnects the moment it fires, so a 1,000-card page is not left holding 1,000 live
 * observers.
 *
 * Under reduced motion it reports revealed immediately and never observes anything at all.
 */
export function useRevealOnScroll<T extends HTMLElement>(): RevealResult<T> {
  const reduced = useReducedMotion();
  const ref = useRef<T>(null);
  const [revealed, setRevealed] = useState(reduced);

  useEffect(() => {
    if (reduced) {
      setRevealed(true);
      return;
    }
    const element = ref.current;
    // No IntersectionObserver (older browsers, jsdom): show the content rather than hide it.
    if (!element || typeof IntersectionObserver === "undefined") {
      setRevealed(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setRevealed(true);
          observer.disconnect();
        }
      },
      // A small negative bottom margin means the reveal starts just before the element is fully
      // on screen, so it has finished by the time the eye lands on it.
      { rootMargin: "0px 0px -10% 0px", threshold: 0.01 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [reduced]);

  return { ref, revealed };
}

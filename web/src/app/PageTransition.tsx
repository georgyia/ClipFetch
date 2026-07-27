import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useReducedMotion } from "../lib/useReducedMotion";
import styles from "./PageTransition.module.css";

export interface PageTransitionProps {
  children: ReactNode;
}

/**
 * A gentle fade-and-rise on route change.
 *
 * Implemented as a keyed CSS animation rather than with the View Transitions API or a motion
 * library, for three reasons worth recording:
 *
 *   - View Transitions needs the DOM swap to happen synchronously inside
 *     `document.startViewTransition`, which in React means wrapping router state in `flushSync` —
 *     giving up concurrent rendering on every navigation to buy a crossfade.
 *   - A motion library would be the largest dependency in the app for one effect that CSS already
 *     expresses in nine lines.
 *   - Keying on pathname means React remounts the subtree, so the animation restarts reliably —
 *     including on a repeat navigation to the same route from a different link.
 *
 * Under reduced motion the wrapper renders its children untouched: no key, no animation class, and
 * therefore no remount churn either.
 */
export function PageTransition({ children }: PageTransitionProps) {
  const { pathname } = useLocation();
  const reduced = useReducedMotion();

  if (reduced) {
    return <>{children}</>;
  }

  return (
    <div key={pathname} className={styles.page}>
      {children}
    </div>
  );
}

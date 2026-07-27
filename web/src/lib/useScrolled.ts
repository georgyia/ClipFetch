import { useEffect, useState } from "react";

/**
 * Whether the window has scrolled past `threshold`, used to condense the app header.
 *
 * The listener is passive and only ever flips a boolean, so scrolling never blocks on React: a
 * state update happens at the two crossing points, not on every scroll event.
 */
export function useScrolled(threshold = 8): boolean {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const read = () => {
      setScrolled(window.scrollY > threshold);
    };
    read(); // A deep link can restore a scroll position before the first event fires.
    window.addEventListener("scroll", read, { passive: true });
    return () => window.removeEventListener("scroll", read);
  }, [threshold]);

  return scrolled;
}

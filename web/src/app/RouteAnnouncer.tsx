import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

// Maps a pathname to a human page name. First match wins, so specific routes precede general ones.
const TITLES: ReadonlyArray<readonly [RegExp, string]> = [
  [/^\/$/, "Home"],
  [/^\/explore/, "Explore"],
  [/^\/search/, "Search"],
  [/^\/library\/favorites/, "Favorites"],
  [/^\/library\/recent/, "Recently Added"],
  [/^\/library/, "Library"],
  [/^\/downloads/, "Downloads"],
  [/^\/settings/, "Settings"],
  [/^\/collections\/[^/]+/, "Collection"],
  [/^\/collections/, "Collections"],
  [/^\/topics\//, "Topic"],
  [/^\/clip\//, "Clip details"],
  [/^\/watch\//, "Player"],
];

export function titleForPath(pathname: string): string {
  for (const [pattern, title] of TITLES) {
    if (pattern.test(pathname)) {
      return title;
    }
  }
  return "ClipFetch Watch";
}

/**
 * Screen readers do not announce client-side navigation on their own. This updates the document
 * title and pushes the new page name into a polite live region on every route change, so a
 * non-visual user knows where they landed.
 */
export function RouteAnnouncer() {
  const { pathname } = useLocation();
  const [message, setMessage] = useState("");

  useEffect(() => {
    const title = titleForPath(pathname);
    document.title = `${title} · ClipFetch Watch`;
    setMessage(`${title} page`);
  }, [pathname]);

  return (
    <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
      {message}
    </div>
  );
}

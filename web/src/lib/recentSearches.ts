// Recent search terms, persisted per browser. Best-effort: storage failures are swallowed so the
// search box keeps working in private-mode or storage-disabled contexts.

const KEY = "clipfetch.recentSearches";
const MAX = 8;

export function loadRecentSearches(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function pushRecentSearch(term: string): string[] {
  const trimmed = term.trim();
  if (!trimmed) {
    return loadRecentSearches();
  }
  const next = [trimmed, ...loadRecentSearches().filter((item) => item !== trimmed)].slice(0, MAX);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Ignore storage failures; recents are a convenience, not a requirement.
  }
  return next;
}

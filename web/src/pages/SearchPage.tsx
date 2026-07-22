import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useSearch } from "../api/queries";
import { Button } from "../components/Button";
import { ClipGrid } from "../components/ClipGrid";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { loadRecentSearches, pushRecentSearch } from "../lib/recentSearches";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import styles from "./SearchPage.module.css";

const MODES = [
  ["all", "All"],
  ["text", "Text"],
  ["meaning", "Meaning"],
] as const;

// Search across captions, creators, hashtags, and transcripts. Input is debounced; the mode and
// query live in the URL. Semantic ("meaning") mode falls back to text with a clear notice until the
// optional semantic capability is available.
export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const [term, setTerm] = useState(params.get("q") ?? "");
  const mode = params.get("mode") ?? "all";
  const debounced = useDebouncedValue(term, 300);
  const [recents, setRecents] = useState<string[]>(() => loadRecentSearches());

  const query = useSearch(debounced, mode);

  // Reflect the debounced query in the URL and record it as a recent search. Keyed only on the
  // debounced term and mode; params/setParams are stable enough and would cause feedback loops.
  // biome-ignore lint/correctness/useExhaustiveDependencies: run only when the debounced term/mode change
  useEffect(() => {
    const next = new URLSearchParams(params);
    if (debounced.trim()) {
      next.set("q", debounced.trim());
    } else {
      next.delete("q");
    }
    setParams(next, { replace: true });
    if (debounced.trim()) {
      setRecents(pushRecentSearch(debounced));
    }
  }, [debounced, mode]);

  function setMode(next: string) {
    const merged = new URLSearchParams(params);
    merged.set("mode", next);
    setParams(merged, { replace: true });
  }

  const result = query.data?.pages[0];
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  const fellBack = mode === "meaning" && result != null && result.mode_used !== "meaning";

  return (
    <section aria-label="Search" className={styles.search}>
      <h1>Search</h1>
      <input
        className={styles.input}
        type="search"
        value={term}
        placeholder="Search captions, creators, transcripts…"
        aria-label="Search query"
        onChange={(event) => setTerm(event.target.value)}
      />

      <div className={styles.modes} role="group" aria-label="Search mode">
        {MODES.map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={`${styles.mode} ${mode === value ? styles.modeActive : ""}`.trim()}
            aria-pressed={mode === value}
            onClick={() => setMode(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {fellBack ? (
        <p className={styles.banner} role="status">
          Meaning search isn't available yet — showing text matches instead.
        </p>
      ) : null}

      {debounced.trim() === "" ? (
        recents.length > 0 ? (
          <div className={styles.recent}>
            <p className={styles.recentTitle}>Recent searches</p>
            <div className={styles.chips}>
              {recents.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={styles.chip}
                  onClick={() => setTerm(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState
            title="Search your library"
            description="Find clips by caption, creator, hashtag, or transcript."
          />
        )
      ) : query.isLoading ? (
        <LoadingState label="Searching…" />
      ) : query.isError ? (
        <ErrorState title="Search failed" description="Try again in a moment." />
      ) : items.length === 0 ? (
        <EmptyState title="No results" description={`Nothing matched "${debounced.trim()}".`} />
      ) : (
        <div>
          <p className={styles.count} aria-live="polite">
            {result?.total_matched ?? items.length} results for "{debounced.trim()}"
          </p>
          <ClipGrid items={items} label="Search results" />
          {query.hasNextPage ? (
            <div style={{ display: "flex", justifyContent: "center", marginTop: "var(--space-8)" }}>
              <Button onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
                {query.isFetchingNextPage ? "Loading…" : "Load more"}
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

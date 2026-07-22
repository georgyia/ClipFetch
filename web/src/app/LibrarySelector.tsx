import type { ChangeEvent } from "react";
import { useActivateLibrary, useBootstrap } from "../api/queries";
import type { LibrarySummary } from "../api/types";
import styles from "./LibrarySelector.module.css";

function activeId(libraries: LibrarySummary[]): string {
  return libraries.find((library) => library.is_active)?.id ?? "";
}

/** Header control to switch the active library. Hidden until at least one library is registered. */
export function LibrarySelector() {
  const { data } = useBootstrap();
  const activate = useActivateLibrary();

  if (!data || data.libraries.length === 0) {
    return null;
  }

  const libraries = data.libraries;
  function onChange(event: ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value;
    if (next && next !== activeId(libraries)) {
      activate.mutate(next);
    }
  }

  return (
    <div className={styles.selector}>
      <label className={styles.label} htmlFor="library-selector">
        Library
      </label>
      <select
        id="library-selector"
        className={styles.select}
        value={activeId(libraries)}
        onChange={onChange}
        disabled={activate.isPending}
      >
        {libraries.map((library) => (
          <option key={library.id} value={library.id}>
            {library.display_name} ({library.clip_count})
          </option>
        ))}
      </select>
    </div>
  );
}

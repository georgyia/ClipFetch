import { useState } from "react";
import { useDirListing } from "../api/queries";
import { Button } from "./Button";
import styles from "./DirectoryPicker.module.css";

interface DirectoryPickerProps {
  /** Called with the absolute path of the folder the user chose. */
  onChoose: (path: string) => void;
  /** Disable the choose action (e.g. while a registration is in flight). */
  busy?: boolean;
}

/**
 * Navigate the server machine's folders and pick one. The listing is sandboxed to the user's home
 * directory on the server (directory names only — never file contents or paths outside home), so
 * this is safe to expose over the loopback UI. Folders that already hold a ClipFetch catalog are
 * tagged so the user can spot an existing library.
 */
export function DirectoryPicker({ onChoose, busy = false }: DirectoryPickerProps) {
  const [path, setPath] = useState<string | null>(null);
  const { data, isLoading, isError, error } = useDirListing(path);

  return (
    <div className={styles.picker} aria-label="Choose a folder">
      <div className={styles.crumbs}>
        <Button
          variant="ghost"
          onClick={() => setPath(data?.parent ?? null)}
          disabled={!data || data.at_root}
          aria-label="Parent folder"
        >
          ↑ Up
        </Button>
        <span className={styles.cwd} title={data?.cwd ?? ""}>
          {data?.cwd ?? "…"}
        </span>
      </div>

      {isError ? (
        <p className={styles.empty} role="alert">
          {error instanceof Error ? error.message : "Could not read that folder."}
        </p>
      ) : isLoading ? (
        <p className={styles.empty}>Loading…</p>
      ) : data && data.entries.length > 0 ? (
        <ul className={styles.list}>
          {data.entries.map((entry) => (
            <li key={entry.path}>
              <button type="button" className={styles.row} onClick={() => setPath(entry.path)}>
                <span className={styles.icon} aria-hidden="true">
                  🗀
                </span>
                <span className={styles.name}>{entry.name}</span>
                {entry.is_library ? <span className={styles.tag}>Library</span> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.empty}>No sub-folders here.</p>
      )}

      <div className={styles.footer}>
        <span className={styles.hint}>Pick the folder that holds (or should hold) your clips.</span>
        <Button
          variant="primary"
          onClick={() => data && onChoose(data.cwd)}
          disabled={busy || !data}
        >
          Use this folder
        </Button>
      </div>
    </div>
  );
}

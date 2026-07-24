import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  useActivateLibrary,
  useLibraries,
  useRegisterLibrary,
  useRescanLibrary,
  useUnregisterLibrary,
} from "../api/queries";
import { Button } from "../components/Button";
import { DirectoryPicker } from "../components/DirectoryPicker";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import styles from "./LibraryPage.module.css";

// Library management surface. Add a library folder without touching the API (#136), and manage the
// registered libraries (#137). Registration and unregistration never touch the library's files.
export function LibraryPage() {
  const { data, isLoading, isError } = useLibraries();
  const register = useRegisterLibrary();
  const activate = useActivateLibrary();
  const rescan = useRescanLibrary();
  const unregister = useUnregisterLibrary();

  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [rescanStatus, setRescanStatus] = useState<string | null>(null);

  const busyId =
    activate.isPending || rescan.isPending || unregister.isPending
      ? ((activate.variables ?? rescan.variables ?? unregister.variables) as string | undefined)
      : undefined;

  const libraries = data?.libraries ?? [];
  // First run: no libraries yet, so open the add flow straight away.
  useEffect(() => {
    if (!isLoading && !isError && libraries.length === 0) {
      setAdding(true);
    }
  }, [isLoading, isError, libraries.length]);

  async function addLibrary(path: string) {
    const displayName = name.trim() || path.split("/").pop() || "Library";
    try {
      const summary = await register.mutateAsync({ display_name: displayName, path });
      await activate.mutateAsync(summary.id);
      setAdding(false);
      setName("");
    } catch {
      // Error is surfaced from register.error below; keep the picker open to retry.
    }
  }

  async function rescanLibrary(libraryId: string) {
    setRescanStatus(null);
    try {
      const result = await rescan.mutateAsync(libraryId);
      const { inserted, updated, missing } = result.report;
      setRescanStatus(`Rescan complete — ${inserted} new, ${updated} updated, ${missing} missing.`);
    } catch {
      setRescanStatus("Rescan failed. Check the folder still exists and try again.");
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading libraries…" />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Could not reach the server"
        description="ClipFetch Watch runs a local server. Start it and try again."
      />
    );
  }

  const registerMessage =
    register.error instanceof ApiError
      ? register.error.message
      : register.isError
        ? "Could not register that folder."
        : null;

  return (
    <section aria-label="Libraries">
      <div className={styles.header}>
        <h1>Library</h1>
        {!adding ? (
          <Button variant="primary" onClick={() => setAdding(true)}>
            Add a library
          </Button>
        ) : null}
      </div>

      {adding ? (
        <div className={styles.add}>
          <h2 className={styles.addTitle}>Add a library</h2>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="library-name">
              Name (optional)
            </label>
            <input
              id="library-name"
              className={styles.input}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="My reels"
            />
          </div>
          <DirectoryPicker onChoose={addLibrary} busy={register.isPending || activate.isPending} />
          {registerMessage ? (
            <p className={styles.error} role="alert">
              {registerMessage}
            </p>
          ) : null}
          {libraries.length > 0 ? (
            <Button variant="ghost" onClick={() => setAdding(false)}>
              Cancel
            </Button>
          ) : null}
        </div>
      ) : null}

      {libraries.length > 0 ? (
        <>
          <p>
            <Link to="/collections">Manage collections →</Link>
          </p>
          {rescanStatus ? (
            <p className={styles.status} role="status">
              {rescanStatus}
            </p>
          ) : null}
          <ul className={styles.list}>
            {libraries.map((library) => {
              const busy = busyId === library.id;
              return (
                <li key={library.id} className={styles.item}>
                  <div className={styles.itemMain}>
                    <div className={styles.name}>
                      {library.display_name}
                      {library.is_active ? <span className={styles.active}> Active</span> : null}
                    </div>
                    <div className={styles.meta}>
                      {library.clip_count} clips · {library.health}
                    </div>
                  </div>
                  <div className={styles.actions}>
                    {library.is_active ? null : (
                      <Button onClick={() => activate.mutate(library.id)} disabled={busy}>
                        Activate
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      onClick={() => rescanLibrary(library.id)}
                      disabled={busy}
                    >
                      {rescan.isPending && busy ? "Rescanning…" : "Rescan"}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        if (
                          window.confirm(
                            `Remove "${library.display_name}" from ClipFetch? This unregisters it only — your files stay on disk.`,
                          )
                        ) {
                          unregister.mutate(library.id);
                        }
                      }}
                      disabled={busy}
                    >
                      Remove
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
    </section>
  );
}

import { useState } from "react";
import { useBootstrap, useForgetMissing, useMissingClips, useRescanLibrary } from "../api/queries";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { SkeletonList } from "../components/Skeletons";
import { useToast } from "../components/Toast";
import { Icons } from "../components/icons";
import { formatBytes, formatDate } from "../lib/format";
import styles from "./MissingMediaPage.module.css";

/**
 * Triage for clips the catalog knows about whose file is no longer on disk.
 *
 * Indexing marks a vanished file unavailable rather than dropping what is known about it — the
 * right default, since a moved folder must not cost you your metadata — but it means dead records
 * pile up out of sight: every browse view filters them out. This is where you meet them.
 *
 * Two ways out. **Rescan** fixes the common case, a file that moved back or a folder re-indexed.
 * **Forget** is for the rest: it drops the catalog record and never touches a file. The server
 * re-checks presence before forgetting anything, so a stale list here cannot delete a clip that
 * has since come back.
 */
export function MissingMediaPage() {
  const missing = useMissingClips();
  const bootstrap = useBootstrap();
  const rescan = useRescanLibrary();
  const forget = useForgetMissing();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);

  const libraryId = bootstrap.data?.active_library?.id;
  const items = missing.data?.items ?? [];

  function toggle(id: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function runRescan() {
    if (!libraryId) {
      return;
    }
    try {
      await rescan.mutateAsync(libraryId);
      toast("Rescanned the library.", { variant: "success" });
    } catch {
      toast("The rescan could not finish.", { variant: "error" });
    }
  }

  async function runForget(ids: string[]) {
    try {
      const report = await forget.mutateAsync(ids);
      setSelected(new Set());
      setConfirming(false);
      const kept = report.kept.length;
      toast(
        kept > 0
          ? `Forgot ${report.forgotten.length}; kept ${kept} whose file is back on disk.`
          : `Forgot ${report.forgotten.length} record${report.forgotten.length === 1 ? "" : "s"}.`,
        { variant: "success" },
      );
    } catch {
      toast("Those records could not be forgotten.", { variant: "error" });
    }
  }

  if (missing.isLoading) {
    return <SkeletonList label="Looking for missing media" />;
  }
  if (missing.isError) {
    return (
      <ErrorState
        title="Could not check for missing media"
        description="The local server did not answer."
        onRetry={() => missing.refetch()}
        retrying={missing.isFetching}
      />
    );
  }

  if (items.length === 0) {
    return (
      <section aria-label="Missing media">
        <h1>Missing media</h1>
        <EmptyState
          icon={Icons.confirm}
          title="Every clip's file is where it should be"
          description="Nothing in the catalog points at a file that has gone missing."
        />
      </section>
    );
  }

  const total = missing.data?.total ?? items.length;
  const chosen = Array.from(selected);

  return (
    <section aria-label="Missing media">
      <h1>Missing media</h1>
      <p className={styles.lead}>
        {total} clip{total === 1 ? "" : "s"} in the catalog point at a file that is not on disk.
        They stay out of every browse view and cannot be played. If you moved the folder back, a
        rescan is all it takes.
      </p>

      <div className={styles.actions}>
        <Button
          variant="primary"
          icon={Icons.refresh}
          loading={rescan.isPending}
          disabled={!libraryId}
          onClick={runRescan}
        >
          Rescan library
        </Button>
        <Button
          variant="subtle"
          icon={Icons.remove}
          disabled={chosen.length === 0 || forget.isPending}
          onClick={() => setConfirming(true)}
        >
          Forget {chosen.length > 0 ? `${chosen.length} selected` : "selected"}
        </Button>
      </div>

      {confirming ? (
        <div className={styles.confirm} role="alertdialog" aria-label="Confirm forget">
          <p className={styles.confirmText}>
            Forget {chosen.length} record{chosen.length === 1 ? "" : "s"}? This removes what the
            catalog knows about {chosen.length === 1 ? "this clip" : "these clips"} — its caption,
            topics, and enrichment. <strong>No file is deleted</strong>, because these files are
            already gone. If one comes back, re-indexing the library restores the clip.
          </p>
          <div className={styles.actions}>
            <Button
              variant="destructive"
              icon={Icons.remove}
              loading={forget.isPending}
              onClick={() => runForget(chosen)}
            >
              Forget them
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.id} className={styles.item}>
            <label className={styles.pick}>
              <input
                type="checkbox"
                checked={selected.has(item.id)}
                onChange={() => toggle(item.id)}
              />
              <span className="visually-hidden">Select {item.caption ?? item.id}</span>
            </label>
            <div className={styles.body}>
              <p className={styles.caption}>{item.caption?.trim() || item.author || item.id}</p>
              {/* The path is what makes the row actionable: it is the file to go looking for. */}
              <p className={styles.path}>{item.relative_path}</p>
              <p className={styles.meta}>
                {item.author ? `${item.author} · ` : ""}
                added {formatDate(item.downloaded_at)}
                {formatBytes(item.file_size_bytes)
                  ? ` · was ${formatBytes(item.file_size_bytes)}`
                  : ""}
              </p>
            </div>
          </li>
        ))}
      </ul>

      {missing.data?.next_offset != null ? (
        <p className={styles.meta}>
          Showing the first {items.length} of {total}.
        </p>
      ) : null}
    </section>
  );
}

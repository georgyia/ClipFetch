import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useCancelJob, useEnqueueJob, useJobs } from "../api/queries";
import type { Job } from "../api/types";
import { Button } from "../components/Button";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import styles from "./DownloadsPage.module.css";

const ACTIVE = new Set(["queued", "running"]);

function JobRow({ job }: { job: Job }) {
  const cancel = useCancelJob();
  const enqueue = useEnqueueJob();
  const total = job.progress_total ?? 0;
  const current = job.progress_current ?? 0;
  const pct = total > 0 ? Math.round((current / total) * 100) : job.state === "succeeded" ? 100 : 0;
  const firstClip = job.result?.clip_ids?.[0];

  return (
    <li className={styles.job}>
      <div className={styles.jobHead}>
        <span className={styles.permalink} title={job.source_permalink ?? undefined}>
          {job.source_permalink ?? job.kind}
        </span>
        <span className={`${styles.state} ${styles[job.state]}`}>{job.state}</span>
        <div className={styles.actions}>
          {ACTIVE.has(job.state) ? (
            <Button
              variant="ghost"
              onClick={() => cancel.mutate(job.id)}
              disabled={cancel.isPending || job.cancel_requested}
            >
              Cancel
            </Button>
          ) : null}
          {job.state === "failed" && job.source_permalink ? (
            <Button
              variant="ghost"
              onClick={() => enqueue.mutate({ url: job.source_permalink ?? "" })}
              disabled={enqueue.isPending}
            >
              Retry
            </Button>
          ) : null}
        </div>
      </div>

      {job.state === "running" && total > 0 ? (
        // biome-ignore lint/a11y/useFocusableInteractive: a progressbar is a status indicator, not a control
        <div
          className={styles.progressTrack}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className={styles.progressFill} style={{ width: `${pct}%` }} />
        </div>
      ) : null}

      <div className={styles.jobMeta}>
        {job.phase ? <span>{job.phase}</span> : null}
        {total > 0 ? (
          <span>
            {current}/{total}
          </span>
        ) : null}
        {job.attempt > 1 ? <span>attempt {job.attempt}</span> : null}
        {job.error ? <span className={styles.error}>{job.error.message}</span> : null}
        {job.state === "succeeded" ? (
          <span>
            Downloaded {job.result?.downloaded ?? 0}
            {firstClip ? (
              <>
                {" · "}
                <Link to={`/clip/${encodeURIComponent(firstClip)}`}>View</Link>
              </>
            ) : null}
          </span>
        ) : null}
      </div>
    </li>
  );
}

// Downloads: submit a source URL, watch active jobs progress (polled while any is active), and
// review history with retry and result links. The platform matrix is stated honestly.
export function DownloadsPage() {
  const jobs = useJobs();
  const enqueue = useEnqueueJob();
  const [url, setUrl] = useState("");
  const [count, setCount] = useState("1");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      return;
    }
    enqueue.mutate({ url: trimmed, count: Number(count) || 1 });
    setUrl("");
  }

  const all = jobs.data?.jobs ?? [];
  const active = all.filter((job) => ACTIVE.has(job.state));
  const history = all.filter((job) => !ACTIVE.has(job.state));

  return (
    <section aria-label="Downloads">
      <h1>Downloads</h1>

      <form className={styles.form} onSubmit={onSubmit} aria-label="New download">
        <div className={styles.field}>
          <label className={styles.label} htmlFor="download-url">
            Source URL
          </label>
          <input
            id="download-url"
            className={styles.input}
            type="url"
            value={url}
            placeholder="https://www.instagram.com/reel/…"
            onChange={(event) => setUrl(event.target.value)}
          />
        </div>
        <div className={`${styles.field} ${styles.count}`}>
          <label className={styles.label} htmlFor="download-count">
            Count
          </label>
          <input
            id="download-count"
            className={styles.input}
            type="number"
            min={1}
            max={200}
            value={count}
            onChange={(event) => setCount(event.target.value)}
          />
        </div>
        <Button type="submit" variant="primary" disabled={enqueue.isPending || url.trim() === ""}>
          Download
        </Button>
      </form>

      <p className={styles.matrix}>
        <span>
          <strong>Instagram</strong> full support
        </span>
        <span>
          <strong>TikTok</strong> experimental — downloads often blocked
        </span>
        <span>
          <strong>YouTube</strong> unavailable
        </span>
      </p>

      {jobs.isLoading ? (
        <LoadingState label="Loading downloads…" />
      ) : jobs.isError ? (
        <ErrorState title="Could not load downloads" description="Try again in a moment." />
      ) : (
        <>
          <div className={styles.group}>
            <h2 className={styles.groupTitle}>Active ({active.length})</h2>
            {active.length === 0 ? (
              <p className={styles.jobMeta}>No downloads in progress.</p>
            ) : (
              <ul className={styles.list}>
                {active.map((job) => (
                  <JobRow key={job.id} job={job} />
                ))}
              </ul>
            )}
          </div>

          <div className={styles.group}>
            <h2 className={styles.groupTitle}>History</h2>
            {history.length === 0 ? (
              <p className={styles.jobMeta}>Nothing here yet.</p>
            ) : (
              <ul className={styles.list}>
                {history.map((job) => (
                  <JobRow key={job.id} job={job} />
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}

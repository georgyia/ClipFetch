import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import {
  useAccounts,
  useCancelJob,
  useConnectAccount,
  useEnqueueJob,
  useJobs,
} from "../api/queries";
import type { Account, Job } from "../api/types";
import { Button } from "../components/Button";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import styles from "./DownloadsPage.module.css";

const ACTIVE = new Set(["queued", "running"]);

function JobRow({ job }: { job: Job }) {
  const cancel = useCancelJob();
  const enqueue = useEnqueueJob();
  const connect = useConnectAccount();
  const total = job.progress_total ?? 0;
  const current = job.progress_current ?? 0;
  const pct = total > 0 ? Math.round((current / total) * 100) : job.state === "succeeded" ? 100 : 0;
  const firstClip = job.result?.clip_ids?.[0];
  const needsSignIn = job.state === "failed" && job.error?.code === "authentication_required";

  return (
    <li className={styles.job}>
      <div className={styles.jobHead}>
        <span className={styles.permalink} title={job.source_permalink ?? undefined}>
          {job.source_permalink || "Your feed"}
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
          {needsSignIn ? (
            <Button
              variant="ghost"
              onClick={() => connect.mutate("instagram")}
              disabled={connect.isPending}
            >
              Connect account
            </Button>
          ) : job.state === "failed" ? (
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

function AccountBar({ account }: { account: Account | undefined }) {
  const connect = useConnectAccount();
  const state = account?.state ?? "unknown";

  return (
    <div className={styles.account}>
      <span>
        <strong>Instagram</strong>{" "}
        {state === "connected"
          ? "connected ✓"
          : state === "connecting"
            ? "opening sign-in…"
            : state === "no_display"
              ? "sign in via the CLI on this machine"
              : "not connected"}
      </span>
      {state !== "connected" && state !== "no_display" ? (
        <Button
          variant="ghost"
          onClick={() => connect.mutate("instagram")}
          disabled={connect.isPending || state === "connecting"}
        >
          Connect Instagram
        </Button>
      ) : null}
    </div>
  );
}

// Downloads: add reels from your Instagram feed or a single account, watch jobs progress, and review
// history with retry / sign-in recovery. The platform matrix is stated honestly.
export function DownloadsPage() {
  const jobs = useJobs();
  const accounts = useAccounts();
  const enqueue = useEnqueueJob();
  const [source, setSource] = useState<"feed" | "account">("feed");
  const [handle, setHandle] = useState("");
  const [count, setCount] = useState("10");
  const [quality, setQuality] = useState("high");

  const instagram = accounts.data?.accounts.find((a) => a.platform === "instagram");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const cleaned = handle.trim().replace(/^@+/, "");
    if (source === "account" && cleaned === "") {
      return;
    }
    enqueue.mutate({
      url: source === "account" ? `@${cleaned}` : "",
      count: Number(count) || 1,
      quality,
    });
    setHandle("");
  }

  const all = jobs.data?.jobs ?? [];
  const active = all.filter((job) => ACTIVE.has(job.state));
  const history = all.filter((job) => !ACTIVE.has(job.state));

  return (
    <section aria-label="Downloads">
      <h1>Downloads</h1>

      <AccountBar account={instagram} />

      <form className={styles.form} onSubmit={onSubmit} aria-label="Add reels">
        <div className={styles.field}>
          <label className={styles.label} htmlFor="download-source">
            Source
          </label>
          <select
            id="download-source"
            className={styles.input}
            value={source}
            onChange={(event) => setSource(event.target.value as "feed" | "account")}
          >
            <option value="feed">Your Instagram feed</option>
            <option value="account">A single account</option>
          </select>
        </div>

        {source === "account" ? (
          <div className={styles.field}>
            <label className={styles.label} htmlFor="download-handle">
              Account
            </label>
            <input
              id="download-handle"
              className={styles.input}
              type="text"
              value={handle}
              placeholder="@nasa"
              onChange={(event) => setHandle(event.target.value)}
            />
          </div>
        ) : null}

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

        <div className={styles.field}>
          <label className={styles.label} htmlFor="download-quality">
            Quality
          </label>
          <select
            id="download-quality"
            className={styles.input}
            value={quality}
            onChange={(event) => setQuality(event.target.value)}
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <Button
          type="submit"
          variant="primary"
          disabled={enqueue.isPending || (source === "account" && handle.trim() === "")}
        >
          Download
        </Button>
      </form>

      <p className={styles.matrix}>
        <span>
          <strong>Instagram</strong> full support
        </span>
        <span>
          <strong>TikTok</strong> experimental — use the CLI
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

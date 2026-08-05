import { Link } from "react-router-dom";
import { useInsights } from "../api/queries";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { SkeletonList } from "../components/Skeletons";
import { Icons } from "../components/icons";
import { titleize } from "../lib/format";
import styles from "./InsightsPage.module.css";

/** Watch time in the largest unit that still reads precisely. */
export function formatWatchTime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`;
}

/** A bar chart drawn from divs: no chart library, and the numbers stay in the DOM as text. */
function Activity({ days }: { days: { day: string; clips: number }[] }) {
  const peak = Math.max(...days.map((entry) => entry.clips), 1);
  return (
    <ol className={styles.activity} aria-label="Clips played per day">
      {days.map((entry) => (
        <li key={entry.day} className={styles.day}>
          <span
            className={styles.bar}
            style={{ height: `${Math.max(6, (entry.clips / peak) * 100)}%` }}
            aria-hidden="true"
          />
          <span className="visually-hidden">
            {entry.day}: {entry.clips} clip{entry.clips === 1 ? "" : "s"}
          </span>
        </li>
      ))}
    </ol>
  );
}

/**
 * What this library holds, and how much of it you have actually watched.
 *
 * Everything here is computed from data the app already keeps — playback rows and the catalog —
 * and none of it leaves the machine. It exists to *show* consumption rather than to encourage it:
 * no streaks, no goals, no "you're behind". The one nudge is towards the clips you collected and
 * never opened, because that is the only figure with an obvious next action.
 *
 * Every number links to the clips behind it. A statistic you cannot inspect is decoration.
 */
export function InsightsPage() {
  const insights = useInsights();

  if (insights.isLoading) {
    return <SkeletonList label="Reading your library" />;
  }
  if (insights.isError || !insights.data) {
    return (
      <ErrorState
        title="Could not read your library"
        description="The local server did not answer."
        onRetry={() => insights.refetch()}
        retrying={insights.isFetching}
      />
    );
  }

  const { totals, top_creators, top_topics, activity } = insights.data;

  if (totals.clips === 0) {
    return (
      <section aria-label="Insights">
        <h1>Insights</h1>
        <EmptyState
          icon={Icons.trending}
          title="Nothing to summarize yet"
          description="Once your library has clips, this is where you can see what you actually watch."
          action={
            <Link to="/downloads">
              <Button variant="primary" icon={Icons.downloads}>
                Add reels
              </Button>
            </Link>
          }
        />
      </section>
    );
  }

  const watchedShare = Math.round((totals.watched_clips / totals.clips) * 100);

  return (
    <section aria-label="Insights">
      <h1>Insights</h1>
      <p className={styles.lead}>
        Everything below is counted from this library on this device. Nothing is sent anywhere, and
        opening this page records nothing.
      </p>

      <ul className={styles.stats}>
        <li className={styles.stat}>
          <span className={styles.value}>{totals.clips.toLocaleString()}</span>
          <Link className={styles.label} to="/library/recent">
            clips in the library
          </Link>
        </li>
        <li className={styles.stat}>
          <span className={styles.value}>{formatWatchTime(totals.watch_time_seconds)}</span>
          <span className={styles.label}>watched</span>
          <span className={styles.note}>furthest point reached in each clip, counted once</span>
        </li>
        <li className={styles.stat}>
          <span className={styles.value}>{totals.watched_clips.toLocaleString()}</span>
          <Link className={styles.label} to="/library/recent">
            clips opened
          </Link>
          <span className={styles.note}>
            {watchedShare}% of the library · {totals.completed_clips.toLocaleString()} finished
          </span>
        </li>
        <li className={styles.stat}>
          <span className={styles.value}>{totals.unwatched_clips.toLocaleString()}</span>
          <span className={styles.label}>collected, never opened</span>
          {totals.unwatched_clips > 0 ? (
            <Link className={styles.cta} to="/library/recent">
              Start on them →
            </Link>
          ) : null}
        </li>
      </ul>

      <div className={styles.columns}>
        <section className={styles.panel} aria-label="Most played creators">
          <h2 className={styles.panelTitle}>Creators you come back to</h2>
          {top_creators.length === 0 ? (
            <p className={styles.note}>No creator is recorded on these clips.</p>
          ) : (
            <ol className={styles.rank}>
              {top_creators.map((entry) => (
                <li key={entry.creator} className={styles.row}>
                  <Link
                    className={styles.rowName}
                    to={`/explore?creator=${encodeURIComponent(entry.creator)}`}
                  >
                    {entry.creator}
                  </Link>
                  <span className={styles.rowMeta}>
                    {entry.plays} play{entry.plays === 1 ? "" : "s"} · {entry.clips} clip
                    {entry.clips === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className={styles.panel} aria-label="Most played topics">
          <h2 className={styles.panelTitle}>Topics you watch</h2>
          {top_topics.length === 0 ? (
            <p className={styles.note}>
              No topics assigned yet — <code>clipfetch library categorize</code> adds them.
            </p>
          ) : (
            <ol className={styles.rank}>
              {top_topics.map((entry) => (
                <li key={entry.topic} className={styles.row}>
                  <Link
                    className={styles.rowName}
                    to={`/topics/${encodeURIComponent(entry.topic)}`}
                  >
                    {titleize(entry.topic)}
                  </Link>
                  <span className={styles.rowMeta}>
                    {entry.plays} play{entry.plays === 1 ? "" : "s"} · {entry.clips} clip
                    {entry.clips === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className={styles.panel} aria-label="Recent activity">
        <h2 className={styles.panelTitle}>The last 30 days</h2>
        {activity.length === 0 ? (
          <p className={styles.note}>Nothing played in the last 30 days.</p>
        ) : (
          <>
            <Activity days={activity} />
            <p className={styles.note}>
              {activity.reduce((sum, entry) => sum + entry.clips, 0)} clips played across{" "}
              {activity.length} day{activity.length === 1 ? "" : "s"}.
            </p>
          </>
        )}
      </section>
    </section>
  );
}

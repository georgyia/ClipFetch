import { Link, useParams } from "react-router-dom";
import { useClipDetail, useClipList } from "../api/queries";
import { type ClipDetail, posterUrl } from "../api/types";
import { Button } from "../components/Button";
import { ClipRail } from "../components/ClipRail";
import { ErrorState } from "../components/ErrorState";
import { FavoriteButton } from "../components/FavoriteButton";
import { LoadingState } from "../components/LoadingState";
import { QualityBadge } from "../components/QualityBadge";
import { TopicChip } from "../components/TopicChip";
import { compactCount, formatBytes, formatDate, formatDuration } from "../lib/format";
import styles from "./ClipDetailPage.module.css";

function stat(label: string, value: string): { label: string; value: string } | null {
  return value ? { label, value } : null;
}

function statList(clip: ClipDetail) {
  return [
    stat("likes", compactCount(clip.likes) && `${compactCount(clip.likes)} likes`),
    stat("views", compactCount(clip.views) && `${compactCount(clip.views)} views`),
    stat(
      "comments",
      clip.comments_count != null ? `${compactCount(clip.comments_count)} comments` : "",
    ),
    stat("shares", clip.shares != null ? `${compactCount(clip.shares)} shares` : ""),
  ].filter((item): item is { label: string; value: string } => item !== null);
}

function RelatedRail({ clip }: { clip: ClipDetail }) {
  const slug = clip.topics[0] ?? "";
  const query = useClipList(
    ["related", slug],
    (cursor) => {
      const params = new URLSearchParams({ limit: "12", sort: "date" });
      if (cursor) {
        params.set("cursor", cursor);
      }
      return `/api/v1/topics/${encodeURIComponent(slug)}/clips?${params.toString()}`;
    },
    { enabled: slug !== "" },
  );

  const related = (query.data?.pages.flatMap((page) => page.items) ?? []).filter(
    (item) => item.id !== clip.id,
  );
  if (related.length === 0) {
    return null;
  }
  return (
    <div className={styles.section}>
      <ClipRail title="More like this" items={related} seeAllTo={`/topics/${slug}`} />
    </div>
  );
}

// Full-page clip detail: metadata, caption, topics, technical details, enrichment status, source,
// and related clips. Entry point to the vertical player.
export function ClipDetailPage() {
  const { id } = useParams();
  const { data: clip, isLoading, isError } = useClipDetail(id);

  if (isLoading) {
    return <LoadingState label="Loading clip…" />;
  }
  if (isError || !clip) {
    return (
      <ErrorState
        title="Clip not found"
        description="This clip may have been removed from the library."
        action={
          <Link to="/">
            <Button variant="secondary">Back to Home</Button>
          </Link>
        }
      />
    );
  }

  const title = clip.caption?.trim() || clip.author || "Untitled clip";
  return (
    <article>
      <div className={styles.top}>
        <img className={styles.poster} src={posterUrl(clip.id)} alt="" decoding="async" />
        <div className={styles.header}>
          <h1 className={styles.title}>{title}</h1>
          {clip.author ? <p className={styles.byline}>@{clip.author}</p> : null}
          <ul className={styles.stats}>
            {statList(clip).map((item) => (
              <li key={item.label}>{item.value}</li>
            ))}
          </ul>
          <div className={styles.actions}>
            {clip.available ? (
              <Link to={`/watch/${encodeURIComponent(clip.id)}`}>
                <Button variant="primary">▶ Watch</Button>
              </Link>
            ) : (
              <Button variant="primary" disabled>
                Media unavailable
              </Button>
            )}
            <FavoriteButton clipId={clip.id} />
          </div>
          {clip.topics.length > 0 ? (
            <div className={styles.chips}>
              {clip.topics.map((topic) => (
                <Link key={topic} to={`/topics/${encodeURIComponent(topic)}`}>
                  <TopicChip label={topic} />
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {clip.caption ? (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Caption</h2>
          <p className={styles.caption}>{clip.caption}</p>
        </div>
      ) : null}

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Details</h2>
        <dl className={styles.details}>
          <dt>Platform</dt>
          <dd>{clip.platform}</dd>
          <dt>Quality</dt>
          <dd>
            <QualityBadge tier={clip.metadata_state} />
          </dd>
          {formatDuration(clip.duration_seconds) ? (
            <>
              <dt>Duration</dt>
              <dd>{formatDuration(clip.duration_seconds)}</dd>
            </>
          ) : null}
          {formatDate(clip.published_at) ? (
            <>
              <dt>Published</dt>
              <dd>{formatDate(clip.published_at)}</dd>
            </>
          ) : null}
          <dt>Added</dt>
          <dd>{formatDate(clip.downloaded_at)}</dd>
          {formatBytes(clip.file_size_bytes) ? (
            <>
              <dt>Size</dt>
              <dd>{formatBytes(clip.file_size_bytes)}</dd>
            </>
          ) : null}
          <dt>Transcript</dt>
          <dd>{clip.has_transcript ? (clip.transcript_status ?? "available") : "not available"}</dd>
          <dt>Comments</dt>
          <dd>{clip.has_comments ? (clip.comment_status ?? "available") : "not available"}</dd>
          {clip.source_url ? (
            <>
              <dt>Source</dt>
              <dd>
                <a
                  className={styles.sourceLink}
                  href={clip.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View original
                </a>
              </dd>
            </>
          ) : null}
        </dl>
      </div>

      <RelatedRail clip={clip} />
    </article>
  );
}

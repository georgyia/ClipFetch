import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useClipDetail, useRelated } from "../api/queries";
import { type ClipDetail, posterUrl } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { ClipRail } from "../components/ClipRail";
import { CommentsPanel } from "../components/CommentsPanel";
import { EnrichActions } from "../components/EnrichActions";
import { ErrorState } from "../components/ErrorState";
import { FavoriteButton } from "../components/FavoriteButton";
import { Icon } from "../components/Icon";
import { QualityBadge } from "../components/QualityBadge";
import { SkeletonClipDetail } from "../components/Skeletons";
import { TopicChip } from "../components/TopicChip";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { Icons, type LucideIcon } from "../components/icons";
import { compactCount, formatBytes, formatDate, formatDuration } from "../lib/format";
import { watchLink } from "../lib/queueSource";
import styles from "./ClipDetailPage.module.css";

/** Long captions collapse to this many characters before a "Show more" appears. */
const CAPTION_CLAMP = 320;

interface Stat {
  key: string;
  icon: LucideIcon;
  value: string;
}

/** Engagement figures as icon chips. Anything the platform did not report is simply omitted. */
function statList(clip: ClipDetail): Stat[] {
  const stats: Stat[] = [];
  const likes = compactCount(clip.likes);
  if (likes) {
    stats.push({ key: "likes", icon: Icons.favorite, value: likes });
  }
  const views = compactCount(clip.views);
  if (views) {
    stats.push({ key: "views", icon: Icons.views, value: views });
  }
  if (clip.comments_count != null) {
    stats.push({
      key: "comments",
      icon: Icons.comments,
      value: compactCount(clip.comments_count) ?? "0",
    });
  }
  const duration = formatDuration(clip.duration_seconds);
  if (duration) {
    stats.push({ key: "duration", icon: Icons.recent, value: duration });
  }
  const published = formatDate(clip.published_at);
  if (published) {
    stats.push({ key: "published", icon: Icons.published, value: published });
  }
  return stats;
}

function Caption({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > CAPTION_CLAMP;
  const shown = expanded || !isLong ? text : `${text.slice(0, CAPTION_CLAMP).trimEnd()}…`;

  return (
    <div className={styles.section}>
      <h2 className={styles.sectionTitle}>Caption</h2>
      <p className={styles.caption}>{shown}</p>
      {isLong ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "Show less" : "Show more"}
        </Button>
      ) : null}
    </div>
  );
}

function RelatedRail({ clip }: { clip: ClipDetail }) {
  const { data } = useRelated(clip.id);
  const related = data?.items ?? [];
  if (related.length === 0) {
    return null;
  }
  const seeAll = clip.topics[0] ? `/topics/${encodeURIComponent(clip.topics[0])}` : undefined;
  return (
    <div className={styles.section}>
      <ClipRail title="More like this" items={related} seeAllTo={seeAll} />
    </div>
  );
}

/**
 * The clip's title page: an ambient backdrop built from its own poster, the crisp portrait media
 * over it, a prominent Play, and metadata as chips — then caption, technical details, and a
 * related rail below.
 */
export function ClipDetailPage() {
  const { id } = useParams();
  const { data: clip, isLoading, isError, isFetching, refetch } = useClipDetail(id);

  if (isLoading) {
    return <SkeletonClipDetail />;
  }
  if (isError || !clip) {
    return (
      <ErrorState
        title="Clip not found"
        description="This clip may have been removed from the library, or the id in the link is stale."
        onRetry={() => refetch()}
        retrying={isFetching}
        action={
          <Link to="/">
            <Button variant="secondary" icon={Icons.home}>
              Back to Home
            </Button>
          </Link>
        }
      />
    );
  }

  const title = clip.caption?.trim() || clip.author || "Untitled clip";
  const stats = statList(clip);
  /*
   * Playing from the detail page seeds the queue with the clip's own topic, so pressing next
   * continues along something related instead of dropping back to global-recent.
   */
  const playTo = clip.topics[0]
    ? watchLink(clip.id, { from: "topic", key: clip.topics[0] })
    : watchLink(clip.id, { from: "recent" });

  return (
    <article className={styles.page}>
      {/*
        Ambient backdrop: the clip's own poster, blown up, blurred, and dimmed. Purely decorative,
        and it sits under a scrim that keeps everything above it at AA contrast whatever the
        poster happens to look like.
      */}
      <div className={styles.backdrop} aria-hidden="true">
        <img className={styles.backdropImage} src={posterUrl(clip.id)} alt="" decoding="async" />
        <div className={styles.backdropScrim} />
      </div>

      <div className={styles.top}>
        <div className={styles.posterFrame}>
          <img className={styles.poster} src={posterUrl(clip.id)} alt="" decoding="async" />
          {clip.available ? null : <span className={styles.unavailable}>Media unavailable</span>}
        </div>

        <div className={styles.header}>
          <div className={styles.badges}>
            <Badge tone="neutral" icon={Icons.clip}>
              {clip.platform}
            </Badge>
            <QualityBadge
              tier={clip.media?.tier.slug ?? "unknown"}
              label={clip.media?.tier.label}
              reason={clip.media?.tier.reason}
            />
            {clip.has_transcript ? (
              <Badge tone="info" icon={Icons.confirm}>
                Transcript
              </Badge>
            ) : null}
          </div>

          <h1 className={styles.title}>{title}</h1>
          {clip.author ? <p className={styles.byline}>@{clip.author}</p> : null}

          {stats.length > 0 ? (
            <ul className={styles.stats}>
              {stats.map((item) => (
                <li key={item.key} className={styles.stat}>
                  <Icon icon={item.icon} size="sm" />
                  {item.value}
                </li>
              ))}
            </ul>
          ) : null}

          <div className={styles.actions}>
            {clip.available ? (
              <Link to={playTo} className={styles.playLink}>
                <Button variant="primary" size="lg" icon={Icons.play}>
                  Play
                </Button>
              </Link>
            ) : (
              <Button variant="primary" size="lg" disabled>
                Media unavailable
              </Button>
            )}
            <FavoriteButton clipId={clip.id} />
            {clip.source_url ? (
              <a
                className={styles.sourceButton}
                href={clip.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Icon icon={Icons.openExternal} size="sm" />
                View original
              </a>
            ) : null}
          </div>

          {clip.topics.length > 0 || clip.hashtags.length > 0 ? (
            <div className={styles.chips}>
              {clip.topics.map((topic) => (
                <TopicChip key={topic} label={topic} linkToTopic />
              ))}
              {clip.hashtags.slice(0, 6).map((tag) => (
                <Chip key={tag} icon={Icons.topics}>
                  {tag.replace(/^#/, "")}
                </Chip>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {clip.caption ? <Caption text={clip.caption} /> : null}

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Details</h2>
        <dl className={styles.details}>
          <dt>Platform</dt>
          <dd>{clip.platform}</dd>
          {clip.media?.height ? (
            <>
              <dt>Resolution</dt>
              <dd>
                {clip.media.width ?? "?"}×{clip.media.height}
                {clip.media.video_codec ? ` · ${clip.media.video_codec}` : ""}
              </dd>
            </>
          ) : null}
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
        </dl>
      </div>

      {/*
        Both panels render nothing when the clip carries no enrichment, rather than an empty box —
        so the actions below are how you ask for it in the first place.
      */}
      <EnrichActions clip={clip} />
      <TranscriptPanel clip={clip} />
      <CommentsPanel clip={clip} />

      <RelatedRail clip={clip} />
    </article>
  );
}

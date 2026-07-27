import { Link } from "react-router-dom";
import { type ClipSummary, mediaUrl, posterUrl } from "../api/types";
import { compactCount, formatDuration } from "../lib/format";
import { useHoverPreview } from "../lib/useHoverPreview";
import styles from "./ClipCard.module.css";
import { Icon } from "./Icon";
import { Icons } from "./icons";

export interface ClipCardProps {
  clip: ClipSummary;
  /** Playback progress in the range 0–1, if this clip is partly watched. */
  progress?: number;
}

/**
 * Author and like count. The heart is an icon rather than a `♥` in the string so it renders the
 * same on every platform, and it stays out of the accessible name — the link is already labelled
 * with the caption.
 */
function Subtitle({ clip }: { clip: ClipSummary }) {
  const likes = compactCount(clip.likes);
  if (!clip.author && !likes) {
    return null;
  }
  return (
    <p className={styles.sub}>
      {clip.author ? <span className={styles.author}>{clip.author}</span> : null}
      {likes ? (
        <span className={styles.stat}>
          <Icon icon={Icons.favorite} size="xs" />
          {likes}
        </span>
      ) : null}
    </p>
  );
}

/**
 * Portrait clip poster with a Netflix-style hover preview: dwell on the card and its muted video
 * plays inline over the poster, the card lifts, and a play affordance appears. Falls back to the
 * static poster on touch, reduced-motion, or unavailable media.
 */
export function ClipCard({ clip, progress }: ClipCardProps) {
  const duration = formatDuration(clip.duration_seconds);
  const label = clip.caption?.trim() || clip.author || "Untitled clip";
  const clamped = progress == null ? null : Math.max(0, Math.min(1, progress));
  const preview = useHoverPreview();
  const showPreview = preview.active && clip.available;
  const wrapClass = `${styles.posterWrap} ${clip.available ? "" : styles.unavailable}`.trim();

  return (
    <Link
      to={`/clip/${encodeURIComponent(clip.id)}`}
      className={styles.card}
      aria-label={label}
      onPointerEnter={preview.onPointerEnter}
      onPointerLeave={preview.onPointerLeave}
      onPointerCancel={preview.onPointerCancel}
    >
      <div className={wrapClass}>
        <img
          className={styles.poster}
          src={posterUrl(clip.id)}
          alt=""
          loading="lazy"
          decoding="async"
          draggable={false}
        />
        {showPreview ? (
          <video
            className={styles.preview}
            src={mediaUrl(clip.id)}
            poster={posterUrl(clip.id)}
            muted
            loop
            autoPlay
            playsInline
            preload="auto"
            onCanPlay={(event) => {
              event.currentTarget.play().catch(() => {});
            }}
            data-testid="hover-preview"
          />
        ) : null}
        <div className={styles.hoverScrim} aria-hidden="true" />
        <span className={styles.playBadge}>
          <Icon icon={Icons.play} size="lg" className={styles.playGlyph} />
        </span>
        {clip.available ? null : <span className={styles.unavailableTag}>Media unavailable</span>}
        {duration ? <span className={styles.duration}>{duration}</span> : null}
        {clamped != null ? (
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: `${clamped * 100}%` }} />
          </div>
        ) : null}
      </div>
      <div className={styles.meta}>
        <p className={styles.caption}>{label}</p>
        <Subtitle clip={clip} />
      </div>
    </Link>
  );
}

import { Link } from "react-router-dom";
import { type ClipSummary, posterUrl } from "../api/types";
import { compactCount, formatDuration } from "../lib/format";
import styles from "./ClipCard.module.css";

export interface ClipCardProps {
  clip: ClipSummary;
  /** Playback progress in the range 0–1, if this clip is partly watched. */
  progress?: number;
}

function subtitle(clip: ClipSummary): string {
  const parts: string[] = [];
  if (clip.author) {
    parts.push(clip.author);
  }
  const likes = compactCount(clip.likes);
  if (likes) {
    parts.push(`♥ ${likes}`);
  }
  return parts.join(" · ");
}

/** Portrait clip poster with lazy image, quality/availability state, and progress. */
export function ClipCard({ clip, progress }: ClipCardProps) {
  const duration = formatDuration(clip.duration_seconds);
  const label = clip.caption?.trim() || clip.author || "Untitled clip";
  const clamped = progress == null ? null : Math.max(0, Math.min(1, progress));
  const wrapClass = `${styles.posterWrap} ${clip.available ? "" : styles.unavailable}`.trim();

  return (
    <Link to={`/clip/${encodeURIComponent(clip.id)}`} className={styles.card} aria-label={label}>
      <div className={wrapClass}>
        <img
          className={styles.poster}
          src={posterUrl(clip.id)}
          alt=""
          loading="lazy"
          decoding="async"
          draggable={false}
        />
        <div className={styles.badges} />
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
        <p className={styles.sub}>{subtitle(clip)}</p>
      </div>
    </Link>
  );
}

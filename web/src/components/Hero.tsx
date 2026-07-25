import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type ClipSummary, mediaUrl, posterUrl } from "../api/types";
import { compactCount } from "../lib/format";
import { previewSuppressed } from "../lib/useHoverPreview";
import styles from "./Hero.module.css";

export interface HeroProps {
  clip: ClipSummary;
  eyebrow?: string;
}

/**
 * Featured billboard for the top of Home: a cinematic still that quietly comes to life with a muted
 * autoplay preview (skipped on touch, reduced-motion, or missing media), a coral→violet wash, and
 * an explicit Play call to action.
 */
export function Hero({ clip, eyebrow = "Featured" }: HeroProps) {
  const title = clip.caption?.trim() || clip.author || "Featured clip";
  const bits = [clip.author, clip.views != null ? `${compactCount(clip.views)} views` : ""].filter(
    Boolean,
  );
  const detail = `/clip/${encodeURIComponent(clip.id)}`;
  const [preview, setPreview] = useState(false);

  useEffect(() => {
    setPreview(false);
    if (!clip.id || !clip.available || previewSuppressed()) {
      return;
    }
    // A short beat before the billboard animates, so the page settles first.
    const timer = window.setTimeout(() => setPreview(true), 1100);
    return () => window.clearTimeout(timer);
  }, [clip.id, clip.available]);

  return (
    <section className={styles.hero} aria-label={title}>
      <img className={styles.poster} src={posterUrl(clip.id)} alt="" decoding="async" />
      {preview ? (
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
          data-testid="hero-preview"
        />
      ) : null}
      <div className={styles.wash} aria-hidden="true" />
      <div className={styles.scrim} aria-hidden="true" />
      <div className={styles.content}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1 className={styles.title}>{title}</h1>
        {bits.length > 0 ? <p className={styles.sub}>{bits.join(" · ")}</p> : null}
        <div className={styles.actions}>
          <Link className={styles.play} to={detail}>
            <span aria-hidden="true">▶</span> Play
          </Link>
          <Link className={styles.info} to={detail}>
            More info
          </Link>
        </div>
      </div>
    </section>
  );
}

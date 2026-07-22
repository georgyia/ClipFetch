import { Link } from "react-router-dom";
import { type ClipSummary, posterUrl } from "../api/types";
import { compactCount } from "../lib/format";
import styles from "./Hero.module.css";

export interface HeroProps {
  clip: ClipSummary;
  eyebrow?: string;
}

/** Featured spotlight for the top of Home; links into the clip detail experience. */
export function Hero({ clip, eyebrow = "Featured" }: HeroProps) {
  const title = clip.caption?.trim() || clip.author || "Featured clip";
  const bits = [clip.author, clip.views != null ? `${compactCount(clip.views)} views` : ""].filter(
    Boolean,
  );

  return (
    <Link to={`/clip/${encodeURIComponent(clip.id)}`} className={styles.hero} aria-label={title}>
      <img className={styles.poster} src={posterUrl(clip.id)} alt="" decoding="async" />
      <div className={styles.scrim} />
      <div className={styles.content}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1 className={styles.title}>{title}</h1>
        {bits.length > 0 ? <p className={styles.sub}>{bits.join(" · ")}</p> : null}
      </div>
    </Link>
  );
}

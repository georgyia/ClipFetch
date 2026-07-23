import styles from "./Badge.module.css";

export interface QualityBadgeProps {
  /** Tier slug from the probed media block: unknown | sd | hd | full_hd | uhd. */
  tier: string;
  /** Human label; falls back to a slug-derived label. */
  label?: string;
  /** Why this tier was assigned (e.g. "1080x1920 source"); shown as a tooltip. */
  reason?: string;
}

const FALLBACK_LABELS: Record<string, string> = {
  unknown: "Unknown",
  sd: "SD",
  hd: "HD",
  full_hd: "Full HD",
  uhd: "4K",
};

// A technical-quality badge measured from the probed file — distinct from a download preference.
export function QualityBadge({ tier, label, reason }: QualityBadgeProps) {
  const text = label ?? FALLBACK_LABELS[tier] ?? "Unknown";
  return (
    <span className={`${styles.badge} ${styles.quality}`} title={reason ?? `Quality: ${text}`}>
      {text}
    </span>
  );
}

import styles from "./Badge.module.css";

const LABELS: Record<string, string> = {
  unknown: "Unknown",
  standard: "SD",
  hd: "HD",
  full_hd: "Full HD",
  higher: "4K+",
  best_available: "Best available",
};

export interface QualityBadgeProps {
  tier: string;
}

export function QualityBadge({ tier }: QualityBadgeProps) {
  const label = LABELS[tier] ?? "Unknown";
  return (
    <span className={`${styles.badge} ${styles.quality}`} title={`Quality: ${label}`}>
      {label}
    </span>
  );
}

import styles from "./Badge.module.css";

export interface TopicChipProps {
  label: string;
}

function titleize(slug: string): string {
  return slug
    .split("-")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

export function TopicChip({ label }: TopicChipProps) {
  return <span className={`${styles.badge} ${styles.chip}`}>{titleize(label)}</span>;
}

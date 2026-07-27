import type { ReactNode } from "react";
import styles from "./Badge.module.css";
import { Icon } from "./Icon";
import type { LucideIcon } from "./icons";

/** Tones map to meaning, so the same colour never means two different things across the app. */
export type BadgeTone = "neutral" | "accent" | "violet" | "success" | "warning" | "danger" | "info";

export interface BadgeProps {
  tone?: BadgeTone;
  icon?: LucideIcon;
  /** Native tooltip text; also becomes the accessible description. */
  title?: string;
  className?: string;
  children: ReactNode;
}

/**
 * A static, non-interactive label: quality tiers, availability, platform, counts. For anything
 * clickable use `Chip` instead — the two share a size and radius so they line up in a row.
 */
export function Badge({ tone = "neutral", icon, title, className, children }: BadgeProps) {
  const classes = [styles.badge, styles[tone], className].filter(Boolean).join(" ");
  return (
    <span className={classes} title={title}>
      {icon ? <Icon icon={icon} size="xs" /> : null}
      {children}
    </span>
  );
}

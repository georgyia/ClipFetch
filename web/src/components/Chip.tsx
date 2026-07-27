import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import styles from "./Chip.module.css";
import { Icon } from "./Icon";
import { Icons, type LucideIcon } from "./icons";

export interface ChipProps {
  children: ReactNode;
  icon?: LucideIcon;
  /** Trailing count, e.g. how many clips carry this topic. Rendered in a dimmed pill. */
  count?: number | null;
  /** Toggle state. When defined the chip becomes a toggle button with `aria-pressed`. */
  selected?: boolean;
  onToggle?: () => void;
  /** Navigation target. Mutually exclusive with `onToggle`. */
  to?: string;
  /** Renders a dismiss affordance — used by the active-filter row. */
  onRemove?: () => void;
  removeLabel?: string;
  disabled?: boolean;
  className?: string;
}

/**
 * An interactive pill: topic links, filter toggles, and dismissible active filters. Shares the
 * badge's radius and height so a row can mix static badges and live chips without looking ragged.
 *
 * The dismiss control is a real nested button, so it is reachable on its own tab stop rather than
 * being a click target hidden inside the chip.
 */
export function Chip({
  children,
  icon,
  count,
  selected,
  onToggle,
  to,
  onRemove,
  removeLabel,
  disabled,
  className,
}: ChipProps) {
  const classes = [
    styles.chip,
    selected ? styles.selected : null,
    onToggle || to ? styles.interactive : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const inner = (
    <>
      {icon ? <Icon icon={icon} size="xs" /> : null}
      <span className={styles.label}>{children}</span>
      {count != null ? <span className={styles.count}>{count}</span> : null}
    </>
  );

  if (onRemove) {
    return (
      <span className={`${classes} ${styles.removable}`}>
        {inner}
        <button
          type="button"
          className={styles.remove}
          onClick={onRemove}
          aria-label={removeLabel ?? "Remove filter"}
        >
          <Icon icon={Icons.close} size="xs" />
        </button>
      </span>
    );
  }

  if (to) {
    return (
      <Link to={to} className={classes}>
        {inner}
      </Link>
    );
  }

  if (onToggle) {
    return (
      <button
        type="button"
        className={classes}
        aria-pressed={selected ?? false}
        disabled={disabled}
        onClick={onToggle}
      >
        {inner}
      </button>
    );
  }

  return <span className={classes}>{inner}</span>;
}

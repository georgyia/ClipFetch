import type { ReactNode } from "react";
import { Icon } from "./Icon";
import styles from "./StateMessage.module.css";
import { Icons, type LucideIcon } from "./icons";

export interface EmptyStateProps {
  title: string;
  description?: string;
  /** Defaults to a neutral inbox mark; pass something specific to the surface where it helps. */
  icon?: LucideIcon;
  action?: ReactNode;
  /** Secondary suggestions — recent searches, example topics — shown under the action. */
  children?: ReactNode;
}

/**
 * A zero-state that tells the user what to do next, not just that there is nothing here.
 *
 * The icon sits in a gradient-washed medallion so the state reads as a designed destination rather
 * than a failure. Copy stays honest about what the app can actually do — no empty state should
 * promise a capability the platform does not have.
 */
export function EmptyState({
  title,
  description,
  icon = Icons.empty,
  action,
  children,
}: EmptyStateProps) {
  return (
    <div className={styles.state}>
      <span className={styles.medallion} aria-hidden="true">
        <Icon icon={icon} size="xl" />
      </span>
      <h2 className={styles.title}>{title}</h2>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.actions}>{action}</div> : null}
      {children ? <div className={styles.extra}>{children}</div> : null}
    </div>
  );
}

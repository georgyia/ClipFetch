import type { ReactNode } from "react";
import { Button } from "./Button";
import { Icon } from "./Icon";
import styles from "./StateMessage.module.css";
import { Icons } from "./icons";

export interface ErrorStateProps {
  title: string;
  /**
   * A sanitized, user-facing explanation. Never pass a raw exception, a stack, or a filesystem
   * path — the server already returns a safe message envelope for anything worth showing.
   */
  description?: string;
  /** Wiring this up renders a Retry button; most callers should, since most errors are transient. */
  onRetry?: () => void;
  retrying?: boolean;
  action?: ReactNode;
}

/**
 * A recoverable-failure card. `role="alert"` so it is announced the moment it replaces the content
 * it was standing in for.
 */
export function ErrorState({ title, description, onRetry, retrying, action }: ErrorStateProps) {
  return (
    <div className={`${styles.state} ${styles.error}`} role="alert">
      <span className={`${styles.medallion} ${styles.medallionError}`} aria-hidden="true">
        <Icon icon={Icons.warning} size="xl" />
      </span>
      <h2 className={styles.title}>{title}</h2>
      {description ? <p className={styles.description}>{description}</p> : null}
      {onRetry || action ? (
        <div className={styles.actions}>
          {onRetry ? (
            <Button variant="primary" icon={Icons.refresh} loading={retrying} onClick={onRetry}>
              Try again
            </Button>
          ) : null}
          {action}
        </div>
      ) : null}
    </div>
  );
}

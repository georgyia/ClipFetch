import styles from "./StateMessage.module.css";

export interface LoadingStateProps {
  label?: string;
}

// Route-level busy indicator. Announced politely to assistive tech via role="status".
export function LoadingState({ label = "Loading…" }: LoadingStateProps) {
  return (
    <div className={styles.state} role="status">
      <p className={styles.description}>{label}</p>
    </div>
  );
}

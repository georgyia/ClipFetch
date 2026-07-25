import { type ReactNode, createContext, useCallback, useContext, useRef, useState } from "react";
import styles from "./Toast.module.css";

export type ToastVariant = "info" | "success" | "error";

export interface ToastOptions {
  variant?: ToastVariant;
}

type ToastFn = (message: string, options?: ToastOptions) => void;

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

// Default no-op so components calling useToast() outside a provider (e.g. isolated unit tests)
// render without crashing — the toast simply doesn't show.
const ToastContext = createContext<ToastFn>(() => {});

/** Fire a transient, screen-reader-announced notification. Safe to call anywhere under the app. */
export function useToast(): ToastFn {
  return useContext(ToastContext);
}

const AUTO_DISMISS_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback<ToastFn>(
    (message, options) => {
      nextId.current += 1;
      const id = nextId.current;
      setItems((prev) => [...prev, { id, message, variant: options?.variant ?? "info" }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className={styles.region} role="status" aria-live="polite" aria-label="Notifications">
        {items.map((item) => (
          <div key={item.id} className={`${styles.toast} ${styles[item.variant]}`}>
            <span className={styles.message}>{item.message}</span>
            <button
              type="button"
              className={styles.dismiss}
              aria-label="Dismiss notification"
              onClick={() => dismiss(item.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

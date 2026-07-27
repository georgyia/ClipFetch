import { useSyncExternalStore } from "react";

/** What the user picked. "system" defers to the OS and keeps tracking it as it changes. */
export type ThemeChoice = "system" | "light" | "dark";
/** What is actually painted right now. */
export type ResolvedTheme = "light" | "dark";

/**
 * Shared with the bootstrap snippet in index.html, which reads the same key before first paint so
 * there is no flash of the wrong theme. Change one and you must change the other.
 */
export const THEME_STORAGE_KEY = "clipfetch-theme";

const DARK_QUERY = "(prefers-color-scheme: dark)";

export interface ThemeState {
  choice: ThemeChoice;
  resolved: ResolvedTheme;
}

/*
 * A module-level store rather than React context: the theme is genuinely global, is read before
 * React mounts (the bootstrap script), and is needed by leaf components like the Settings toggle.
 * A store means no provider to thread through the tree — and no test that has to remember to wrap.
 */
const listeners = new Set<() => void>();
let state: ThemeState = initialState();

function isChoice(value: unknown): value is ThemeChoice {
  return value === "system" || value === "light" || value === "dark";
}

/** Storage can throw in private modes or locked-down browsers; failures fall back to system. */
export function readStoredChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return isChoice(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

function prefersDark(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(DARK_QUERY).matches
    : true; // Dark is the product default, so it is also the answer when we cannot ask.
}

export function resolveTheme(choice: ThemeChoice): ResolvedTheme {
  if (choice === "system") {
    return prefersDark() ? "dark" : "light";
  }
  return choice;
}

function initialState(): ThemeState {
  const choice = typeof window === "undefined" ? "system" : readStoredChoice();
  return { choice, resolved: resolveTheme(choice) };
}

/**
 * Writes the theme to the document element. `color-scheme` is set alongside `data-theme` so native
 * widgets — scrollbars, form controls, the mobile URL bar — follow the app rather than the OS.
 */
function applyTheme(resolved: ResolvedTheme): void {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
}

function setState(next: ThemeState): void {
  state = next;
  applyTheme(next.resolved);
  for (const listener of listeners) {
    listener();
  }
}

/** Change the theme and persist it. */
export function setThemeChoice(choice: ThemeChoice): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // A blocked or full store is not worth failing the interaction over — the choice still
    // applies for this session, it just will not survive a reload.
  }
  setState({ choice, resolved: resolveTheme(choice) });
}

/** Re-reads storage and the OS preference. Exported for tests. */
export function refreshTheme(): void {
  const choice = readStoredChoice();
  setState({ choice, resolved: resolveTheme(choice) });
}

// While the choice is "system", follow the OS as the user flips it — no reload required.
if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
  window.matchMedia(DARK_QUERY).addEventListener("change", () => {
    if (state.choice === "system") {
      setState({ choice: "system", resolved: prefersDark() ? "dark" : "light" });
    }
  });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): ThemeState {
  return state;
}

export interface UseThemeResult extends ThemeState {
  setChoice: (choice: ThemeChoice) => void;
}

export function useTheme(): UseThemeResult {
  const current = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  return { ...current, setChoice: setThemeChoice };
}

import { useEffect, useState } from "react";
import { Dialog } from "./Dialog";
import styles from "./ShortcutsHelp.module.css";

interface Shortcut {
  keys: string[];
  action: string;
}

const GLOBAL: Shortcut[] = [{ keys: ["?"], action: "Show this help" }];

const PLAYER: Shortcut[] = [
  { keys: ["Space", "K"], action: "Play / pause" },
  { keys: ["←", "→"], action: "Seek 5s back / forward" },
  { keys: ["P", "N"], action: "Previous / next in queue" },
  { keys: ["M"], action: "Mute / unmute" },
  { keys: ["S"], action: "Toggle shuffle" },
  { keys: ["Q"], action: "Toggle the up-next queue" },
  { keys: ["Esc"], action: "Back out of the player" },
];

const BROWSING: Shortcut[] = [{ keys: ["←", "→"], action: "Move between cards in a row" }];

function Section({ title, shortcuts }: { title: string; shortcuts: Shortcut[] }) {
  return (
    <div className={styles.section}>
      <h3 className={styles.sectionTitle}>{title}</h3>
      <dl className={styles.list}>
        {shortcuts.map((shortcut) => (
          <div key={shortcut.action} className={styles.row}>
            <dt className={styles.keys}>
              {shortcut.keys.map((key) => (
                <kbd key={key} className={styles.key}>
                  {key}
                </kbd>
              ))}
            </dt>
            <dd className={styles.action}>{shortcut.action}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * A global "?" opens a keyboard-shortcuts cheat sheet. Ignored while typing in a field, so "?" in a
 * search box still types a question mark.
 */
export function ShortcutsHelp() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "?") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) {
        return;
      }
      event.preventDefault();
      setOpen((value) => !value);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <Dialog open={open} onClose={() => setOpen(false)} title="Keyboard shortcuts">
      <Section title="Anywhere" shortcuts={GLOBAL} />
      <Section title="Browsing" shortcuts={BROWSING} />
      <Section title="Player" shortcuts={PLAYER} />
    </Dialog>
  );
}

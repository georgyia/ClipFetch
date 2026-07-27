import { closeShortcutsHelp, useShortcutsHelpOpen } from "../lib/overlays";
import { Dialog } from "./Dialog";
import styles from "./ShortcutsHelp.module.css";

interface Shortcut {
  keys: string[];
  action: string;
}

const GLOBAL: Shortcut[] = [
  { keys: ["⌘K", "Ctrl+K"], action: "Open the command palette" },
  { keys: ["?"], action: "Show this help" },
];

const PALETTE: Shortcut[] = [
  { keys: ["↑", "↓"], action: "Move between results" },
  { keys: ["↵"], action: "Run the highlighted command" },
  { keys: ["Esc"], action: "Close the palette" },
];

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
 * The keyboard cheat sheet. Open state lives in the shared overlay store, so both the global "?"
 * binding and the command palette's "Show keyboard shortcuts" action drive the same dialog.
 */
export function ShortcutsHelp() {
  const open = useShortcutsHelpOpen();

  return (
    <Dialog open={open} onClose={closeShortcutsHelp} title="Keyboard shortcuts">
      <Section title="Anywhere" shortcuts={GLOBAL} />
      <Section title="Command palette" shortcuts={PALETTE} />
      <Section title="Browsing" shortcuts={BROWSING} />
      <Section title="Player" shortcuts={PLAYER} />
    </Dialog>
  );
}

import { useEffect } from "react";
import { toggleCommandPalette, toggleShortcutsHelp } from "./overlays";

/** Fields where a bare keypress means "type this character", not "run a command". */
function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) {
    return false;
  }
  return /^(INPUT|TEXTAREA|SELECT)$/.test(element.tagName) || element.isContentEditable === true;
}

/**
 * App-wide keyboard entry points.
 *
 *   ⌘K / Ctrl+K   command palette — deliberately *does* fire while typing, because a modifier
 *                 combination is unambiguous and reaching the palette from a search box is the
 *                 whole point of it.
 *   ?             shortcuts sheet — a bare key, so it is ignored inside any text field; otherwise
 *                 typing "?" in the search box would open a dialog instead of a question mark.
 */
export function useGlobalShortcuts(): void {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggleCommandPalette();
        return;
      }
      if (event.key === "?" && !isTypingTarget(event.target)) {
        event.preventDefault();
        toggleShortcutsHelp();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}

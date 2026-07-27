import { type RefObject, useEffect } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
}

export interface FocusTrapOptions {
  /** Called on Escape. The overlay owns what "close" means. */
  onClose: () => void;
  /**
   * Skip moving focus into the panel on open. The command palette sets this: it focuses its own
   * input, and a trap that grabbed the first focusable element would fight that.
   */
  skipInitialFocus?: boolean;
}

/**
 * Trap Tab within `containerRef` while `open`, close on Escape, and restore focus on unmount.
 *
 * Shared by the Dialog and the command palette so there is one implementation of the rules rather
 * than two that drift. The keydown listener is registered in the capture phase so it sees Escape
 * before a descendant can stop it, and `stopPropagation` keeps a nested overlay from closing its
 * parent as well.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement>,
  open: boolean,
  { onClose, skipInitialFocus = false }: FocusTrapOptions,
): void {
  useEffect(() => {
    if (!open) {
      return;
    }
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const container = containerRef.current;

    if (!skipInitialFocus && container) {
      (focusableWithin(container)[0] ?? container).focus();
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !container) {
        return;
      }
      const items = focusableWithin(container);
      if (items.length === 0) {
        // Nothing to move to; keep focus where it is rather than letting it escape the overlay.
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      // Return the user to whatever opened the overlay, not to the top of the document.
      previouslyFocused?.focus();
    };
  }, [open, onClose, containerRef, skipInitialFocus]);
}

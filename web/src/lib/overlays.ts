import { useSyncExternalStore } from "react";

/**
 * Open/closed state for the app's global overlays — the command palette and the shortcuts sheet.
 *
 * These live outside the React tree for the same reason the theme does: they are opened from
 * keyboard handlers on `window`, from the header, and from each other (the palette offers "Show
 * keyboard shortcuts"). Threading that through context would mean a provider wrapping the app and
 * a callback prop on every path in between.
 */
function createToggleStore() {
  const listeners = new Set<() => void>();
  let open = false;

  const emit = () => {
    for (const listener of listeners) {
      listener();
    }
  };

  return {
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    get: () => open,
    set(next: boolean) {
      if (open === next) {
        return;
      }
      open = next;
      emit();
    },
    toggle() {
      open = !open;
      emit();
    },
  };
}

const paletteStore = createToggleStore();
const shortcutsStore = createToggleStore();

export const openCommandPalette = () => paletteStore.set(true);
export const closeCommandPalette = () => paletteStore.set(false);
export const toggleCommandPalette = () => paletteStore.toggle();

export const openShortcutsHelp = () => shortcutsStore.set(true);
export const closeShortcutsHelp = () => shortcutsStore.set(false);
export const toggleShortcutsHelp = () => shortcutsStore.toggle();

export function useCommandPaletteOpen(): boolean {
  return useSyncExternalStore(paletteStore.subscribe, paletteStore.get, paletteStore.get);
}

export function useShortcutsHelpOpen(): boolean {
  return useSyncExternalStore(shortcutsStore.subscribe, shortcutsStore.get, shortcutsStore.get);
}

/** Reset both overlays. Exported for tests, which share module state between cases. */
export function resetOverlays(): void {
  paletteStore.set(false);
  shortcutsStore.set(false);
}

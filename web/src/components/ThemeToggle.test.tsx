import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test } from "vitest";
import { THEME_STORAGE_KEY, refreshTheme, resolveTheme } from "../lib/theme";
import { ThemeToggle } from "./ThemeToggle";

/** Point matchMedia at a fixed OS preference so "system" resolution is deterministic. */
function stubSystemPrefersDark(dark: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: dark && query.includes("dark"),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

beforeEach(() => {
  localStorage.clear();
  stubSystemPrefersDark(true);
  refreshTheme();
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

test("renders all three states with system selected by default", () => {
  render(<ThemeToggle />);
  expect(screen.getByRole("radio", { name: /System/ })).toBeChecked();
  expect(screen.getByRole("radio", { name: "Light" })).not.toBeChecked();
  expect(screen.getByRole("radio", { name: "Dark" })).not.toBeChecked();
});

test("choosing light applies data-theme and persists it", () => {
  render(<ThemeToggle />);
  fireEvent.click(screen.getByRole("radio", { name: "Light" }));

  expect(document.documentElement.dataset.theme).toBe("light");
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  expect(screen.getByRole("radio", { name: "Light" })).toBeChecked();
});

test("a persisted choice is restored on the next load", () => {
  localStorage.setItem(THEME_STORAGE_KEY, "dark");
  refreshTheme();
  render(<ThemeToggle />);

  expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
  expect(document.documentElement.dataset.theme).toBe("dark");
});

test("system follows the OS preference in both directions", () => {
  stubSystemPrefersDark(false);
  expect(resolveTheme("system")).toBe("light");
  stubSystemPrefersDark(true);
  expect(resolveTheme("system")).toBe("dark");
  // An explicit choice ignores the OS entirely.
  expect(resolveTheme("light")).toBe("light");
});

test("an unreadable stored value falls back to system rather than throwing", () => {
  localStorage.setItem(THEME_STORAGE_KEY, "chartreuse");
  refreshTheme();
  render(<ThemeToggle />);
  expect(screen.getByRole("radio", { name: /System/ })).toBeChecked();
});

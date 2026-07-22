import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView; rail keyboard navigation calls it.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

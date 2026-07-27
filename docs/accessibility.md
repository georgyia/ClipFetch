# Accessibility in ClipFetch Watch

Accessibility is a release gate for Watch, not a follow-up task. This page records what the
interface commits to, how each commitment is *verified*, and what is deliberately not claimed.

The target is **WCAG 2.2 AA**.

---

## Contents

- [What is asserted in the test suite](#what-is-asserted-in-the-test-suite)
- [Keyboard operation](#keyboard-operation)
- [Focus management](#focus-management)
- [Screen-reader behaviour](#screen-reader-behaviour)
- [Motion](#motion)
- [Colour and contrast](#colour-and-contrast)
- [Target sizes](#target-sizes)
- [Known gaps](#known-gaps)

---

## What is asserted in the test suite

These are checks that fail the build, not manual habits:

| Area | Test |
|---|---|
| Contrast, both themes | `web/src/styles/contrast.test.ts` parses `tokens.css` and computes WCAG ratios |
| Focus trap and restoration | `web/src/components/CommandPalette.test.tsx` |
| Reduced motion | `web/src/app/PageTransition.test.tsx` |
| Route announcements | `web/src/app/RouteAnnouncer.test.tsx` |
| Icon labelling | `web/src/components/Icon.test.tsx` |
| Loading announcements | `web/src/components/Skeletons.test.tsx` |
| Player controls and shortcuts | `web/src/pages/PlayerPage.test.tsx` |

Run them with `npm --prefix web test`.

---

## Keyboard operation

Every interactive control is reachable and operable from the keyboard.

**Global bindings.** `⌘K` / `Ctrl+K` opens the command palette; `?` opens the shortcuts sheet.

Bare-key shortcuts are ignored while focus is in a text field, so `?` in a search box types a
question mark. `⌘K` deliberately still fires there — a modifier chord is unambiguous, and reaching
the palette from a search box is a normal thing to want.

**The command palette** follows the ARIA combobox-with-listbox pattern. Focus stays on the input;
the highlighted row is pointed at with `aria-activedescendant`. Options carry `tabindex="-1"` so
they are programmatically focusable without joining the tab order, and group headings are
`role="presentation"` so a screen reader walks past them to the next real option. Pointer movement
drives the same highlight the arrow keys do, so mouse and keyboard can never disagree about which
row `Enter` would run.

**The player** keeps a full key map (see the [user guide](watch-user-guide.md)). Its scrubber is a
real `<input type="range">` with the visual bars painted underneath, so native keyboard seeking and
value announcements work rather than being re-implemented.

**Rails** support arrow-key movement between cards.

---

## Focus management

`useFocusTrap` is the single implementation, shared by the Dialog and the command palette:

- Tab and Shift+Tab wrap within the open overlay.
- `Escape` closes it, with `stopPropagation` so a nested overlay does not also close its parent.
- On close, focus returns to whatever opened the overlay.

The palette registers the trap *before* the effect that focuses its search input, because the trap
records the previously-focused element when it runs — the other order would capture the palette's
own input and restore focus to nothing. There is a test for exactly this.

Focus is visible everywhere via the shared `--ring` token. Controls that sit on their own background
(player buttons, chips) draw the ring as a `box-shadow` so it follows their radius rather than
being clipped.

The skip link (`Skip to content`) is the first tab stop on every page.

---

## Screen-reader behaviour

**Route changes** are announced. Client-side navigation is invisible to a screen reader by default,
so `RouteAnnouncer` sets the document title and pushes the page name into a polite live region on
every route change.

**Icons are decorative by default.** The `Icon` wrapper applies `aria-hidden` unless the caller
passes a label, so an icon sitting beside visible text is never announced twice. Icon-only controls
carry an `aria-label` instead.

**Loading is announced once per surface.** Skeleton placeholders are all `aria-hidden`; the
container carries a single polite live region. A screen reader hears "Loading favorites" once
rather than a stream of anonymous boxes. Composed skeletons suppress their children's regions so
several do not compete.

**Errors** use `role="alert"`, so a failure is announced the moment it replaces the content it was
standing in for.

**State is exposed, not implied.** Toggles use `aria-pressed`, disclosures use `aria-expanded`, the
theme control is a labelled radio group, and filter facets are `role="group"` with names.

---

## Motion

`prefers-reduced-motion` is honoured at two levels.

**CSS** neutralises transitions and animations globally, and `--motion-scale` drops to `0` so a
single declaration can flatten itself with `calc()` instead of needing a duplicate rule:

```css
transform: translateY(calc(-6px * var(--motion-scale)));
```

**JavaScript** goes further, skipping the work rather than running it at a 0.001ms duration:

- `PageTransition` renders children with **no wrapper element at all**.
- `useRevealOnScroll` reports revealed immediately and **never attaches an observer**.
- The player's ambient glow is not rendered.
- The player's controls **do not auto-hide**.

`useRevealOnScroll` also fails open: with no `IntersectionObserver`, content is shown rather than
left hidden.

---

## Colour and contrast

Both themes are derived independently rather than by inversion, and the ratios are asserted against
the shipped `tokens.css` rather than eyeballed. Measured values against each theme's page
background:

| Token | Dark | Light |
|---|---|---|
| `--color-text` | 18.9:1 | 18.3:1 |
| `--color-text-secondary` | 10.6:1 | 7.9:1 |
| `--color-text-muted` | 6.1:1 | 4.7:1 |
| `--color-accent` | 6.2:1 | 5.0:1 |
| `--color-focus` | 12.0:1 | 5.7:1 |

The light theme uses a deepened coral (`#d3253f`) because the dark theme's `#ff4d67` reaches only
about 3:1 on white — short of AA for text.

Colour is never the only signal: quality tiers pair tone with a label, availability states carry
text, and active filters are listed explicitly rather than only being highlighted.

Scrims over media are contrast devices rather than decoration. The hero, clip-detail backdrop, and
card overlays all place a gradient between the media and any text on top of it, so legibility does
not depend on what a particular poster happens to look like.

---

## Target sizes

The `--hit-target` token is 44px and every interactive control honours it.

Filter chips are visually 34px so a facet row stays dense, but extend their *pointer* target back
to 44px with a pseudo-element — density without failing WCAG 2.5.8.

---

## Known gaps

Stated plainly rather than papered over:

- **No captions or subtitles in the player.** Transcripts exist in the catalog and are surfaced on
  the clip detail page, but they are not yet rendered as timed text over the video.
- **The player scrubber has no thumbnail preview**, only a time preview. Position-accurate
  thumbnails need a sprite-sheet endpoint the backend does not expose, and showing the same poster
  at every scrub position would be misleading.
- **No automated axe/Lighthouse run in CI.** Coverage today is targeted unit assertions plus manual
  keyboard and screen-reader passes from the [release checklist](release-checklist.md).
- **Screen-reader testing is spot-check only** — VoiceOver on macOS. NVDA and JAWS have not been
  exercised.

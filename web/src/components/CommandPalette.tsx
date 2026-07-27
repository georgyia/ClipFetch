import { Fragment, useEffect, useId, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCollections, useSearch, useTopics } from "../api/queries";
import { NAV_ITEMS } from "../app/navItems";
import { rank } from "../lib/fuzzy";
import { closeCommandPalette, openShortcutsHelp, useCommandPaletteOpen } from "../lib/overlays";
import { loadRecentSearches } from "../lib/recentSearches";
import { setThemeChoice } from "../lib/theme";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import styles from "./CommandPalette.module.css";
import { Icon } from "./Icon";
import { Icons, type LucideIcon } from "./icons";

/** How many clip results the palette will show inline. Bounded on purpose — see below. */
const MAX_CLIP_RESULTS = 5;
const MAX_PER_GROUP = 6;

type CommandGroup = "Go to" | "Topics" | "Collections" | "Actions" | "Search" | "Clips";

interface Command {
  id: string;
  group: CommandGroup;
  label: string;
  hint?: string;
  icon: LucideIcon;
  /** Extra text folded into matching but never displayed — synonyms and aliases. */
  keywords?: string;
  run: () => void;
}

export function CommandPalette() {
  const open = useCommandPaletteOpen();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const optionId = useId();

  const topics = useTopics();
  const collections = useCollections();

  /*
   * Inline clip results are debounced and capped, and the query only runs while the palette is
   * open with something typed — a palette must never turn keystrokes into a request per character.
   */
  const debouncedQuery = useDebouncedValue(query, 220);
  const clipQuery = useSearch(
    open && debouncedQuery.trim().length > 1 ? debouncedQuery : "",
    "all",
  );
  const clipResults = useMemo(
    () => (clipQuery.data?.pages[0]?.items ?? []).slice(0, MAX_CLIP_RESULTS),
    [clipQuery.data],
  );

  const run = useMemo(
    () => (action: () => void) => () => {
      closeCommandPalette();
      action();
    },
    [],
  );

  /** Everything the palette can do, before filtering. */
  const commands = useMemo<Command[]>(() => {
    const items: Command[] = NAV_ITEMS.map((item) => ({
      id: `nav:${item.to}`,
      group: "Go to" as const,
      label: item.label,
      hint: item.hint,
      icon: item.icon,
      run: run(() => navigate(item.to)),
    }));

    for (const topic of topics.data?.topics ?? []) {
      items.push({
        id: `topic:${topic.slug}`,
        group: "Topics",
        label: topic.slug.replace(/-/g, " "),
        hint: `${topic.clip_count} clip${topic.clip_count === 1 ? "" : "s"}`,
        icon: Icons.topics,
        run: run(() => navigate(`/topics/${encodeURIComponent(topic.slug)}`)),
      });
    }

    for (const collection of collections.data?.collections ?? []) {
      items.push({
        id: `collection:${collection.id}`,
        group: "Collections",
        label: collection.id,
        hint: `${collection.clip_count} clip${collection.clip_count === 1 ? "" : "s"}`,
        icon: Icons.collections,
        run: run(() => navigate(`/collections/${encodeURIComponent(collection.id)}`)),
      });
    }

    items.push(
      {
        id: "action:add-reels",
        group: "Actions",
        label: "Add reels",
        hint: "Queue a download",
        icon: Icons.downloads,
        keywords: "download fetch grab new",
        run: run(() => navigate("/downloads")),
      },
      {
        id: "action:add-library",
        group: "Actions",
        label: "Add a library",
        hint: "Register a folder of clips",
        icon: Icons.folderOpen,
        keywords: "register folder open",
        run: run(() => navigate("/library")),
      },
      {
        id: "action:connect",
        group: "Actions",
        label: "Connect an account",
        hint: "Sign in to a platform",
        icon: Icons.openExternal,
        keywords: "instagram sign in login account",
        run: run(() => navigate("/settings")),
      },
      {
        id: "action:shortcuts",
        group: "Actions",
        label: "Show keyboard shortcuts",
        hint: "?",
        icon: Icons.keyboard,
        keywords: "keys help bindings cheat sheet",
        run: run(openShortcutsHelp),
      },
      {
        id: "action:theme-system",
        group: "Actions",
        label: "Theme: System",
        hint: "Follow the operating system",
        icon: Icons.themeSystem,
        keywords: "appearance colour color dark light auto",
        run: run(() => setThemeChoice("system")),
      },
      {
        id: "action:theme-light",
        group: "Actions",
        label: "Theme: Light",
        icon: Icons.themeLight,
        keywords: "appearance colour color bright",
        run: run(() => setThemeChoice("light")),
      },
      {
        id: "action:theme-dark",
        group: "Actions",
        label: "Theme: Dark",
        icon: Icons.themeDark,
        keywords: "appearance colour color night",
        run: run(() => setThemeChoice("dark")),
      },
    );

    return items;
  }, [navigate, run, topics.data, collections.data]);

  /*
   * The visible list: ranked commands, then a "search for this" escape hatch, then any inline clip
   * matches. Each group is capped so a large library cannot push the actions off the bottom.
   */
  const visible = useMemo<Command[]>(() => {
    const trimmed = query.trim();
    const ranked = rank(query, commands, (command) =>
      `${command.group} ${command.label} ${command.keywords ?? ""}`.trim(),
    );

    const byGroup = new Map<CommandGroup, Command[]>();
    for (const { item } of ranked) {
      const bucket = byGroup.get(item.group) ?? [];
      if (bucket.length < MAX_PER_GROUP) {
        bucket.push(item);
        byGroup.set(item.group, bucket);
      }
    }

    const order: CommandGroup[] = ["Go to", "Actions", "Topics", "Collections"];
    const result = order.flatMap((group) => byGroup.get(group) ?? []);

    if (trimmed) {
      result.unshift({
        id: "search:query",
        group: "Search",
        label: `Search for “${trimmed}”`,
        icon: Icons.search,
        run: run(() => navigate(`/search?q=${encodeURIComponent(trimmed)}`)),
      });
      for (const clip of clipResults) {
        result.push({
          id: `clip:${clip.id}`,
          group: "Clips",
          label: clip.caption?.trim() || clip.author || "Untitled clip",
          hint: clip.author ?? undefined,
          icon: Icons.clip,
          run: run(() => navigate(`/clip/${encodeURIComponent(clip.id)}`)),
        });
      }
      return result;
    }

    // Empty query: offer recent searches ahead of the default command list.
    const recents = loadRecentSearches()
      .slice(0, 3)
      .map<Command>((term) => ({
        id: `recent:${term}`,
        group: "Search",
        label: term,
        hint: "Recent search",
        icon: Icons.recent,
        run: run(() => navigate(`/search?q=${encodeURIComponent(term)}`)),
      }));
    return [...recents, ...result];
  }, [query, commands, clipResults, navigate, run]);

  // Reset the query each time the palette opens, so it never reopens mid-thought.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
    }
  }, [open]);

  // Keep the highlighted row in range as the list shrinks under a narrowing query.
  useEffect(() => {
    setActiveIndex((index) => Math.min(index, Math.max(0, visible.length - 1)));
  }, [visible.length]);

  useEffect(() => {
    if (!open) {
      return;
    }
    inputRef.current?.focus();
  }, [open]);

  /*
   * Scroll the active row into view for keyboard-only navigation. Looked up by id rather than by
   * child index, because group headings are interleaved into the list as presentation rows and
   * would otherwise throw the indexing off.
   */
  useEffect(() => {
    document.getElementById(`${optionId}-${activeIndex}`)?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, optionId]);

  if (!open) {
    return null;
  }

  const active = visible[activeIndex];

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (visible.length ? (index + 1) % visible.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) =>
        visible.length ? (index - 1 + visible.length) % visible.length : 0,
      );
    } else if (event.key === "Home") {
      event.preventDefault();
      setActiveIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActiveIndex(Math.max(0, visible.length - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      active?.run();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeCommandPalette();
    }
  }

  /*
   * The list uses the ARIA combobox-with-listbox pattern: focus never leaves the input, and the
   * active option is pointed at with aria-activedescendant. Options carry tabindex="-1" so they
   * are programmatically focusable without joining the tab order, and group headings are
   * role="presentation" so a screen reader walks straight past them to the next real option.
   */
  let lastGroup: CommandGroup | null = null;

  return (
    <div className={styles.backdrop}>
      <button
        type="button"
        className={styles.backdropButton}
        aria-label="Close command palette"
        onClick={closeCommandPalette}
      />
      <div className={styles.panel} role="dialog" aria-modal="true" aria-label="Command palette">
        <div className={styles.inputRow}>
          <Icon icon={Icons.search} size="lg" className={styles.inputIcon} />
          <input
            ref={inputRef}
            className={styles.input}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls={listboxId}
            aria-activedescendant={active ? `${optionId}-${activeIndex}` : undefined}
            aria-autocomplete="list"
            aria-label="Search commands, topics, and clips"
            placeholder="Jump to a page, topic, or clip…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className={styles.escHint}>Esc</kbd>
        </div>

        {visible.length === 0 ? (
          <p className={styles.empty}>
            Nothing matches “{query.trim()}”. Press Enter to search your library instead.
          </p>
        ) : (
          <div className={styles.list} id={listboxId} role="listbox" ref={listRef} tabIndex={-1}>
            {visible.map((command, index) => {
              const showHeading = command.group !== lastGroup;
              lastGroup = command.group;
              const isActive = index === activeIndex;
              return (
                <Fragment key={command.id}>
                  {showHeading ? (
                    <div role="presentation" className={styles.heading}>
                      {command.group}
                    </div>
                  ) : null}
                  {/* biome-ignore lint/a11y/useKeyWithClickEvents: keyboard activation is handled once on the combobox input (Enter runs the aria-activedescendant row); a per-option key handler would never fire, since focus never leaves the input. */}
                  <div
                    id={`${optionId}-${index}`}
                    role="option"
                    tabIndex={-1}
                    aria-selected={isActive}
                    className={`${styles.option} ${isActive ? styles.optionActive : ""}`.trim()}
                    // Pointer moves drive the same highlight the arrow keys do, so mouse and
                    // keyboard never disagree about which row Enter would run. Keyboard activation
                    // is handled once, on the input, so there is no per-option key handler.
                    onPointerMove={() => setActiveIndex(index)}
                    onClick={command.run}
                  >
                    <Icon icon={command.icon} size="md" className={styles.optionIcon} />
                    <span className={styles.optionLabel}>{command.label}</span>
                    {command.hint ? (
                      <span className={styles.optionHint}>{command.hint}</span>
                    ) : null}
                  </div>
                </Fragment>
              );
            })}
          </div>
        )}

        <div className={styles.footer}>
          <span>
            <kbd className={styles.key}>↑</kbd>
            <kbd className={styles.key}>↓</kbd> to navigate
          </span>
          <span>
            <kbd className={styles.key}>↵</kbd> to select
          </span>
          <span>
            <kbd className={styles.key}>?</kbd> for shortcuts
          </span>
        </div>
      </div>
    </div>
  );
}

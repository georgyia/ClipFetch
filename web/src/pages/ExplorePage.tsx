import { type FormEvent, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useClipList, useTopics } from "../api/queries";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { ClipListView } from "../components/ClipListView";
import { Icon } from "../components/Icon";
import { Icons } from "../components/icons";
import { titleize } from "../lib/format";
import styles from "./ExplorePage.module.css";

const SORTS = [
  ["date", "Newest"],
  ["likes", "Most liked"],
  ["views", "Most viewed"],
  ["author", "Creator A–Z"],
] as const;

const PLATFORMS = [
  ["instagram", "Instagram"],
  ["tiktok", "TikTok"],
] as const;

const MIN_LIKES = [
  ["1000", "1K+"],
  ["10000", "10K+"],
  ["100000", "100K+"],
  ["1000000", "1M+"],
] as const;

/** Topics shown as chips before the rest fold into a select. */
const TOPIC_CHIP_LIMIT = 10;

/** The active filters as API query parameters — shared by the listing and the export. */
function filterQuery(params: URLSearchParams): URLSearchParams {
  const query = new URLSearchParams({ sort: params.get("sort") || "date" });
  for (const field of ["topic", "platform", "creator"] as const) {
    const value = params.get(field);
    if (value) {
      query.set(field, value);
    }
  }
  const minLikes = params.get("min_likes");
  if (minLikes) {
    query.set("min_likes", minLikes);
  }
  return query;
}

function buildPath(params: URLSearchParams, cursor: string | null): string {
  const query = filterQuery(params);
  query.set("limit", "24");
  if (cursor) {
    query.set("cursor", cursor);
  }
  return `/api/v1/clips?${query.toString()}`;
}

/**
 * The same filters pointed at the export endpoint, so what downloads is what the page shows —
 * the whole match set, not only the pages scrolled into view.
 */
function exportPath(params: URLSearchParams): string {
  const query = filterQuery(params);
  query.set("name", params.get("topic") || params.get("creator") || "explore");
  return `/api/v1/clips/export?${query.toString()}`;
}

interface ActiveFilter {
  field: string;
  label: string;
}

/** The filters currently narrowing the view, as dismissible chips. Sort is not a filter. */
function activeFilters(params: URLSearchParams, topicLabel: (slug: string) => string) {
  const active: ActiveFilter[] = [];
  const topic = params.get("topic");
  if (topic) {
    active.push({ field: "topic", label: topicLabel(topic) });
  }
  const platform = params.get("platform");
  if (platform) {
    const match = PLATFORMS.find(([value]) => value === platform);
    active.push({ field: "platform", label: match?.[1] ?? platform });
  }
  const minLikes = params.get("min_likes");
  if (minLikes) {
    const match = MIN_LIKES.find(([value]) => value === minLikes);
    active.push({ field: "min_likes", label: `${match?.[1] ?? minLikes} likes` });
  }
  const creator = params.get("creator");
  if (creator) {
    active.push({ field: "creator", label: `@${creator}` });
  }
  return active;
}

/**
 * Explore: narrow the library by topic, platform, creator, popularity, and sort.
 *
 * Every facet is a chip, and all filter state lives in the URL — views are shareable, the back
 * button restores them, and the same params seed the player's queue so a filtered set becomes
 * something you can binge.
 */
export function ExplorePage() {
  const [params, setParams] = useSearchParams();
  const topics = useTopics();
  const [creator, setCreator] = useState(params.get("creator") ?? "");

  function update(next: Record<string, string>) {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value) {
        merged.set(key, value);
      } else {
        merged.delete(key);
      }
    }
    setParams(merged, { replace: true });
  }

  /** Chips toggle: choosing the value that is already set clears it. */
  function toggle(field: string, value: string) {
    update({ [field]: params.get(field) === value ? "" : value });
  }

  function clearAll() {
    // Sort is a view preference rather than a filter, so "Clear all" leaves it alone.
    const sort = params.get("sort");
    setParams(sort ? new URLSearchParams({ sort }) : new URLSearchParams(), { replace: true });
    setCreator("");
  }

  function onSubmitCreator(event: FormEvent) {
    event.preventDefault();
    update({ creator: creator.trim() });
  }

  const allTopics = topics.data?.topics ?? [];
  const topicLabel = (slug: string) => titleize(slug);
  const chipTopics = allTopics.slice(0, TOPIC_CHIP_LIMIT);
  const overflowTopics = allTopics.slice(TOPIC_CHIP_LIMIT);
  const selectedTopic = params.get("topic") ?? "";
  const active = activeFilters(params, topicLabel);

  const key = ["explore", params.toString()];
  const query = useClipList(key, (cursor) => buildPath(params, cursor));

  return (
    <section aria-label="Explore">
      <h1 className={styles.pageTitle}>Explore</h1>

      {/*
        The facet bar sticks below the app header while results scroll, so narrowing a large
        result set never means scrolling back to the top to reach the controls.
      */}
      <div className={styles.stickyBar}>
        <form className={styles.facets} aria-label="Filters" onSubmit={onSubmitCreator}>
          <div className={styles.facetRow} role="group" aria-label="Sort">
            <span className={styles.facetLabel}>
              <Icon icon={Icons.sort} size="xs" />
              Sort
            </span>
            {SORTS.map(([value, label]) => (
              <Chip
                key={value}
                selected={(params.get("sort") ?? "date") === value}
                onToggle={() => update({ sort: value })}
              >
                {label}
              </Chip>
            ))}
          </div>

          {allTopics.length > 0 ? (
            <div className={styles.facetRow} role="group" aria-label="Topic">
              <span className={styles.facetLabel}>
                <Icon icon={Icons.topics} size="xs" />
                Topic
              </span>
              {chipTopics.map((topic) => (
                <Chip
                  key={topic.slug}
                  count={topic.clip_count}
                  selected={selectedTopic === topic.slug}
                  onToggle={() => toggle("topic", topic.slug)}
                >
                  {topicLabel(topic.slug)}
                </Chip>
              ))}
              {overflowTopics.length > 0 ? (
                <select
                  className={styles.overflowSelect}
                  aria-label="More topics"
                  value={
                    overflowTopics.some((topic) => topic.slug === selectedTopic)
                      ? selectedTopic
                      : ""
                  }
                  onChange={(event) => update({ topic: event.target.value })}
                >
                  <option value="">More topics…</option>
                  {overflowTopics.map((topic) => (
                    <option key={topic.slug} value={topic.slug}>
                      {topicLabel(topic.slug)} ({topic.clip_count})
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          ) : null}

          <div className={styles.facetRow} role="group" aria-label="Platform and popularity">
            <span className={styles.facetLabel}>
              <Icon icon={Icons.filter} size="xs" />
              Filter
            </span>
            {PLATFORMS.map(([value, label]) => (
              <Chip
                key={value}
                selected={params.get("platform") === value}
                onToggle={() => toggle("platform", value)}
              >
                {label}
              </Chip>
            ))}
            {MIN_LIKES.map(([value, label]) => (
              <Chip
                key={value}
                icon={Icons.favorite}
                selected={params.get("min_likes") === value}
                onToggle={() => toggle("min_likes", value)}
              >
                {label}
              </Chip>
            ))}
            <label className={styles.creatorField}>
              <span className="visually-hidden">Creator</span>
              <Icon icon={Icons.search} size="xs" />
              <input
                className={styles.creatorInput}
                type="text"
                value={creator}
                placeholder="Creator…"
                onChange={(event) => setCreator(event.target.value)}
                onBlur={() => update({ creator: creator.trim() })}
              />
            </label>
            {/* Submitting the form applies the creator field for keyboard users. */}
            <button type="submit" className="visually-hidden">
              Apply creator filter
            </button>
          </div>
        </form>

        {active.length > 0 ? (
          <div className={styles.activeRow} aria-label="Active filters">
            <span className={styles.facetLabel}>Active</span>
            {active.map((filter) => (
              <Chip
                key={filter.field}
                selected
                onRemove={() => {
                  update({ [filter.field]: "" });
                  if (filter.field === "creator") {
                    setCreator("");
                  }
                }}
                removeLabel={`Remove ${filter.label} filter`}
              >
                {filter.label}
              </Chip>
            ))}
            <Button variant="ghost" size="sm" icon={Icons.close} onClick={clearAll}>
              Clear all
            </Button>
          </div>
        ) : null}
      </div>

      <ClipListView
        title="Results"
        query={query}
        emptyIcon={Icons.filter}
        emptyTitle="No matches"
        emptyDescription="Nothing in your library matches every one of these filters."
        emptyAction={
          active.length > 0 ? (
            <Button variant="primary" icon={Icons.close} onClick={clearAll}>
              Clear all filters
            </Button>
          ) : undefined
        }
        queueContext={{ from: "explore", params }}
        exportPath={exportPath(params)}
      />
    </section>
  );
}

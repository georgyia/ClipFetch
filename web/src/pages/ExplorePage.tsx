import { type FormEvent, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useClipList, useTopics } from "../api/queries";
import { Button } from "../components/Button";
import { ClipListView } from "../components/ClipListView";
import { titleize } from "../lib/format";
import styles from "./ExplorePage.module.css";

const SORTS = [
  ["date", "Newest"],
  ["likes", "Most liked"],
  ["views", "Most viewed"],
  ["author", "Creator A–Z"],
] as const;

const PLATFORMS = [
  ["", "All platforms"],
  ["instagram", "Instagram"],
  ["tiktok", "TikTok"],
] as const;

function buildPath(params: URLSearchParams, cursor: string | null): string {
  const query = new URLSearchParams({ limit: "24", sort: params.get("sort") || "date" });
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
  if (cursor) {
    query.set("cursor", cursor);
  }
  return `/api/v1/clips?${query.toString()}`;
}

// Explore: filter the library by topic, platform, creator, popularity, and sort. All filter state
// lives in the URL so views are shareable and the back button restores them.
export function ExplorePage() {
  const [params, setParams] = useSearchParams();
  const topics = useTopics();
  const [open, setOpen] = useState(false);
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

  function onSubmitCreator(event: FormEvent) {
    event.preventDefault();
    update({ creator: creator.trim() });
  }

  const key = ["explore", params.toString()];
  const query = useClipList(key, (cursor) => buildPath(params, cursor));

  return (
    <section aria-label="Explore">
      <div className={styles.header}>
        <h1>Explore</h1>
        <Button
          className={styles.toggle}
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
        >
          {open ? "Hide filters" : "Filters"}
        </Button>
      </div>

      <form
        className={`${styles.filters} ${open ? "" : styles.collapsed}`.trim()}
        aria-label="Filters"
        onSubmit={onSubmitCreator}
      >
        <div className={styles.field}>
          <label className={styles.label} htmlFor="filter-topic">
            Topic
          </label>
          <select
            id="filter-topic"
            className={styles.control}
            value={params.get("topic") ?? ""}
            onChange={(event) => update({ topic: event.target.value })}
          >
            <option value="">All topics</option>
            {(topics.data?.topics ?? []).map((topic) => (
              <option key={topic.slug} value={topic.slug}>
                {titleize(topic.slug)} ({topic.clip_count})
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="filter-platform">
            Platform
          </label>
          <select
            id="filter-platform"
            className={styles.control}
            value={params.get("platform") ?? ""}
            onChange={(event) => update({ platform: event.target.value })}
          >
            {PLATFORMS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="filter-sort">
            Sort
          </label>
          <select
            id="filter-sort"
            className={styles.control}
            value={params.get("sort") ?? "date"}
            onChange={(event) => update({ sort: event.target.value })}
          >
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="filter-min-likes">
            Min likes
          </label>
          <select
            id="filter-min-likes"
            className={styles.control}
            value={params.get("min_likes") ?? ""}
            onChange={(event) => update({ min_likes: event.target.value })}
          >
            <option value="">Any</option>
            <option value="1000">1K+</option>
            <option value="10000">10K+</option>
            <option value="100000">100K+</option>
            <option value="1000000">1M+</option>
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="filter-creator">
            Creator
          </label>
          <input
            id="filter-creator"
            className={styles.control}
            type="text"
            value={creator}
            placeholder="e.g. chef"
            onChange={(event) => setCreator(event.target.value)}
            onBlur={() => update({ creator: creator.trim() })}
          />
        </div>

        <div className={styles.actions}>
          <Button type="submit">Apply</Button>
        </div>
      </form>

      <ClipListView
        title="Results"
        query={query}
        emptyTitle="No matches"
        emptyDescription="Try relaxing a filter to see more clips."
      />
    </section>
  );
}

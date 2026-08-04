import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  type CollectionFilters,
  useCollections,
  useCreateCollection,
  useDeleteCollection,
  useTopics,
  useUpdateCollection,
} from "../api/queries";
import type { CollectionSummary } from "../api/types";
import { Button } from "../components/Button";
import { ErrorState } from "../components/ErrorState";
import { SkeletonList } from "../components/Skeletons";
import { titleize } from "../lib/format";
import styles from "./CollectionsPage.module.css";

function firstString(value: unknown): string {
  return Array.isArray(value) && typeof value[0] === "string" ? value[0] : "";
}

function toFilters(topic: string, platform: string, minLikes: string): CollectionFilters {
  const filters: CollectionFilters = {};
  if (topic) {
    filters.topics = [topic];
  }
  if (platform) {
    filters.platforms = [platform];
  }
  if (minLikes) {
    filters.min_likes = Number(minLikes);
  }
  return filters;
}

// Manage saved collections: create, edit their filter definition, and delete them. Editing and
// deleting never touch the underlying clips — only the stored definition.
//
// Membership is deliberately explicit here. A *filtered* collection re-evaluates its query on every
// read; a *manual* one has no query at all and holds only what was added to it from a grid or a
// card. Both can hold pinned clips, and pins survive every edit made on this page.
export function CollectionsPage() {
  const collections = useCollections();
  const topics = useTopics();
  const create = useCreateCollection();
  const update = useUpdateCollection();
  const remove = useDeleteCollection();

  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [manual, setManual] = useState(false);
  const [topic, setTopic] = useState("");
  const [platform, setPlatform] = useState("");
  const [minLikes, setMinLikes] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setEditing(null);
    setName("");
    setManual(false);
    setTopic("");
    setPlatform("");
    setMinLikes("");
    setError("");
  }

  function startEdit(collection: CollectionSummary) {
    setEditing(collection.id);
    setName(collection.id);
    setManual(collection.filters === null);
    setTopic(firstString(collection.filters?.topics));
    setPlatform(firstString(collection.filters?.platforms));
    const likes = collection.filters?.min_likes;
    setMinLikes(typeof likes === "number" ? String(likes) : "");
    setError("");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    // null is not an empty filter: an empty filter would match the entire library.
    const filters = manual ? null : toFilters(topic, platform, minLikes);
    try {
      if (editing) {
        await update.mutateAsync({ id: editing, filters });
      } else {
        await create.mutateAsync({ name, filters });
      }
      reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the collection.");
    }
  }

  if (collections.isLoading) {
    return <SkeletonList label="Loading collections" />;
  }
  if (collections.isError || !collections.data) {
    return (
      <ErrorState
        title="Could not load collections"
        description="The local server did not answer."
        onRetry={() => collections.refetch()}
        retrying={collections.isFetching}
      />
    );
  }

  const pending = create.isPending || update.isPending;
  return (
    <section aria-label="Collections">
      <h1>Collections</h1>

      <ul className={styles.list}>
        {collections.data.collections.map((collection) => (
          <li key={collection.id} className={styles.item}>
            <Link to={`/collections/${encodeURIComponent(collection.id)}`} className={styles.name}>
              {titleize(collection.id)}
            </Link>
            <span className={styles.count}>
              {collection.clip_count} clips
              {collection.pinned_count > 0 ? ` · ${collection.pinned_count} added by hand` : ""}
              {collection.filters === null ? " · no filter" : ""}
            </span>
            <span className={styles.spacer} />
            <Button variant="ghost" onClick={() => startEdit(collection)}>
              Edit
            </Button>
            <Button
              variant="ghost"
              onClick={() => remove.mutate(collection.id)}
              disabled={remove.isPending}
            >
              Delete
            </Button>
          </li>
        ))}
      </ul>

      <form className={styles.form} onSubmit={onSubmit} aria-label="Collection editor">
        <div className={styles.field}>
          <label className={styles.label} htmlFor="collection-name">
            Name
          </label>
          <input
            id="collection-name"
            className={styles.control}
            value={name}
            disabled={editing !== null}
            placeholder="e.g. big-hits"
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="collection-membership">
            Membership
          </label>
          <select
            id="collection-membership"
            className={styles.control}
            value={manual ? "manual" : "filtered"}
            onChange={(event) => setManual(event.target.value === "manual")}
          >
            <option value="filtered">Filtered</option>
            <option value="manual">Added by hand</option>
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="collection-topic">
            Topic
          </label>
          <select
            id="collection-topic"
            className={styles.control}
            value={topic}
            disabled={manual}
            onChange={(event) => setTopic(event.target.value)}
          >
            <option value="">Any topic</option>
            {(topics.data?.topics ?? []).map((item) => (
              <option key={item.slug} value={item.slug}>
                {titleize(item.slug)}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="collection-platform">
            Platform
          </label>
          <select
            id="collection-platform"
            className={styles.control}
            value={platform}
            disabled={manual}
            onChange={(event) => setPlatform(event.target.value)}
          >
            <option value="">Any platform</option>
            <option value="instagram">Instagram</option>
            <option value="tiktok">TikTok</option>
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="collection-min-likes">
            Min likes
          </label>
          <select
            id="collection-min-likes"
            className={styles.control}
            value={minLikes}
            disabled={manual}
            onChange={(event) => setMinLikes(event.target.value)}
          >
            <option value="">Any</option>
            <option value="1000">1K+</option>
            <option value="10000">10K+</option>
            <option value="100000">100K+</option>
            <option value="1000000">1M+</option>
          </select>
        </div>
        <div className={styles.actions}>
          <Button type="submit" variant="primary" disabled={pending || (!editing && !name)}>
            {editing ? "Save" : "Create"}
          </Button>
          {editing ? (
            <Button type="button" onClick={reset}>
              Cancel
            </Button>
          ) : null}
        </div>
        <p className={styles.hint}>
          {manual
            ? "No filter: this collection holds only the clips you add to it from a grid or a card."
            : "Filtered: membership is re-evaluated as your library changes. Clips added by hand stay either way."}
          {editing ? "" : " Names use lowercase letters, numbers, and single hyphens."}
        </p>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </form>
    </section>
  );
}

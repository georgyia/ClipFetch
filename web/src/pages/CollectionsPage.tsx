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
import { LoadingState } from "../components/LoadingState";
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

// Manage saved dynamic collections: create, edit their filter definition, and delete them. Editing
// and deleting never touch the underlying clips — only the stored filter.
export function CollectionsPage() {
  const collections = useCollections();
  const topics = useTopics();
  const create = useCreateCollection();
  const update = useUpdateCollection();
  const remove = useDeleteCollection();

  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [platform, setPlatform] = useState("");
  const [minLikes, setMinLikes] = useState("");
  const [error, setError] = useState("");

  function reset() {
    setEditing(null);
    setName("");
    setTopic("");
    setPlatform("");
    setMinLikes("");
    setError("");
  }

  function startEdit(collection: CollectionSummary) {
    setEditing(collection.id);
    setName(collection.id);
    setTopic(firstString(collection.filters.topics));
    setPlatform(firstString(collection.filters.platforms));
    const likes = collection.filters.min_likes;
    setMinLikes(typeof likes === "number" ? String(likes) : "");
    setError("");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const filters = toFilters(topic, platform, minLikes);
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
    return <LoadingState label="Loading collections…" />;
  }
  if (collections.isError || !collections.data) {
    return <ErrorState title="Something went wrong" description="Collections could not load." />;
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
            <span className={styles.count}>{collection.clip_count} clips</span>
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
          <label className={styles.label} htmlFor="collection-topic">
            Topic
          </label>
          <select
            id="collection-topic"
            className={styles.control}
            value={topic}
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
        {editing ? null : (
          <p className={styles.hint}>Names use lowercase letters, numbers, and single hyphens.</p>
        )}
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </form>
    </section>
  );
}

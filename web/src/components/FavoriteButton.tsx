import { useFavorite, useToggleFavorite } from "../api/queries";
import styles from "./FavoriteButton.module.css";
import { Icon } from "./Icon";
import { Icons } from "./icons";

export interface FavoriteButtonProps {
  clipId: string;
  /** Icon-only rendering for dense surfaces such as card overlays. */
  compact?: boolean;
}

/** Toggle a clip's favorite state. Optimistic; reflects the cached favorite flag. */
export function FavoriteButton({ clipId, compact = false }: FavoriteButtonProps) {
  const { data } = useFavorite(clipId);
  const toggle = useToggleFavorite();
  const isFavorite = data?.favorite ?? false;
  const label = isFavorite ? "Favorited" : "Favorite";

  return (
    <button
      type="button"
      className={[styles.button, isFavorite ? styles.active : null, compact ? styles.compact : null]
        .filter(Boolean)
        .join(" ")}
      aria-pressed={isFavorite}
      aria-label={compact ? label : undefined}
      disabled={toggle.isPending}
      onClick={() => toggle.mutate({ clipId, favorite: !isFavorite })}
    >
      <Icon icon={Icons.favorite} size="md" className={isFavorite ? styles.filled : styles.heart} />
      {compact ? null : label}
    </button>
  );
}

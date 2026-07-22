import { useFavorite, useToggleFavorite } from "../api/queries";
import styles from "./FavoriteButton.module.css";

export interface FavoriteButtonProps {
  clipId: string;
}

/** Toggle a clip's favorite state. Optimistic; reflects the cached favorite flag. */
export function FavoriteButton({ clipId }: FavoriteButtonProps) {
  const { data } = useFavorite(clipId);
  const toggle = useToggleFavorite();
  const isFavorite = data?.favorite ?? false;

  return (
    <button
      type="button"
      className={`${styles.button} ${isFavorite ? styles.active : ""}`.trim()}
      aria-pressed={isFavorite}
      disabled={toggle.isPending}
      onClick={() => toggle.mutate({ clipId, favorite: !isFavorite })}
    >
      <span className={styles.heart} aria-hidden="true">
        {isFavorite ? "♥" : "♡"}
      </span>
      {isFavorite ? "Favorited" : "Favorite"}
    </button>
  );
}

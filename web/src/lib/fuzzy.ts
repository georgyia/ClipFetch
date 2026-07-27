/**
 * A small subsequence matcher for the command palette.
 *
 * Deliberately not a general-purpose fuzzy library: the palette ranks a few dozen short, known
 * strings, so the useful behaviour is "typing `dl` finds Downloads" and "an exact prefix wins",
 * not edit-distance scoring. Everything here is O(query × candidate) on strings under ~60 chars.
 */

export interface FuzzyMatch {
  /** Higher is better. Only meaningful for comparing candidates against the same query. */
  score: number;
  /** Indices in the candidate that the query matched, for highlighting. */
  indices: number[];
}

/**
 * Score `candidate` against `query`, or return null when the query is not a subsequence of it.
 *
 * Scoring rewards, in order: a match at the very start, matches at word boundaries (after a space,
 * hyphen, or slash), and runs of consecutive characters. That ordering is what makes short
 * abbreviations behave — "cw" beats a scattered match because both letters land on word starts.
 */
export function fuzzyMatch(query: string, candidate: string): FuzzyMatch | null {
  const q = query.trim().toLowerCase();
  if (!q) {
    return { score: 0, indices: [] };
  }
  const c = candidate.toLowerCase();

  const indices: number[] = [];
  let score = 0;
  let cursor = 0;
  let previousIndex = -1;

  for (const char of q) {
    const found = c.indexOf(char, cursor);
    if (found === -1) {
      return null;
    }

    if (found === 0) {
      score += 12; // matches the first character of the candidate
    } else if (/[\s\-/_.]/.test(c[found - 1])) {
      score += 8; // start of a word
    }
    if (found === previousIndex + 1) {
      score += 6; // continues an unbroken run
    }
    // Later matches are worth slightly less, so early hits rank first among equals.
    score += Math.max(0, 4 - Math.floor(found / 8));

    indices.push(found);
    previousIndex = found;
    cursor = found + 1;
  }

  // Prefer tight matches: the same letters spread across a long label are a weaker signal.
  score -= Math.floor((c.length - q.length) / 12);
  return { score, indices };
}

export interface Ranked<T> {
  item: T;
  score: number;
  indices: number[];
}

/**
 * Filter and rank `items` by `query`. An empty query keeps the caller's original order, which is
 * how the palette shows a curated default list rather than an arbitrary one.
 */
export function rank<T>(query: string, items: T[], toText: (item: T) => string): Ranked<T>[] {
  if (!query.trim()) {
    return items.map((item) => ({ item, score: 0, indices: [] }));
  }
  const matched: Ranked<T>[] = [];
  items.forEach((item, index) => {
    const result = fuzzyMatch(query, toText(item));
    if (result) {
      // Index acts as a stable tiebreaker so equal scores never reshuffle between renders.
      matched.push({ item, score: result.score * 1000 - index, indices: result.indices });
    }
  });
  return matched.sort((a, b) => b.score - a.score);
}

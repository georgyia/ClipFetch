import { Link } from "react-router-dom";
import { useBootstrap } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

// Library management surface. Registration/import flows are separate backlog items; for now this
// lists what is registered and surfaces the active library's health.
export function LibraryPage() {
  const { data, isLoading, isError } = useBootstrap();

  if (isLoading) {
    return <LoadingState label="Loading libraries…" />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Could not reach the server"
        description="ClipFetch Watch runs a local server. Start it and try again."
      />
    );
  }
  if (data.libraries.length === 0) {
    return (
      <EmptyState
        title="No libraries yet"
        description="Register a library folder from the ClipFetch CLI, then reload to browse it here."
      />
    );
  }

  return (
    <section aria-label="Libraries">
      <h1>Library</h1>
      <p>
        <Link to="/collections">Manage collections →</Link>
      </p>
      <ul>
        {data.libraries.map((library) => (
          <li key={library.id}>
            {library.display_name} — {library.clip_count} clips · {library.health}
            {library.is_active ? " · active" : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}

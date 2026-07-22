import { useBootstrap } from "../api/queries";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

// Placeholder home. The composed rails and hero land with the Home browsing work; this keeps the
// route functional and reflects real bootstrap state until then.
export function HomePage() {
  const { data, isLoading, isError } = useBootstrap();

  if (isLoading) {
    return <LoadingState label="Loading your library…" />;
  }
  if (isError || !data) {
    return (
      <ErrorState
        title="Could not reach the ClipFetch Watch server"
        description="Start the local server, then reload this page."
      />
    );
  }
  if (!data.active_library) {
    return (
      <EmptyState
        title="No active library"
        description="Register and activate a library to start watching."
      />
    );
  }

  return (
    <section aria-label="Home">
      <h1>Home</h1>
      <p>
        {data.active_library.display_name} · {data.active_library.clip_count} clips
      </p>
    </section>
  );
}

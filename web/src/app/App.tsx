import { Route, Routes } from "react-router-dom";
import { ClipDetailPage } from "../pages/ClipDetailPage";
import { CollectionDetailPage } from "../pages/CollectionDetailPage";
import { CollectionsPage } from "../pages/CollectionsPage";
import { ComingSoon } from "../pages/ComingSoon";
import { DownloadsPage } from "../pages/DownloadsPage";
import { ExplorePage } from "../pages/ExplorePage";
import { FavoritesPage } from "../pages/FavoritesPage";
import { HomePage } from "../pages/HomePage";
import { LibraryPage } from "../pages/LibraryPage";
import { PlayerPage } from "../pages/PlayerPage";
import { RecentPage } from "../pages/RecentPage";
import { SearchPage } from "../pages/SearchPage";
import { TopicPage } from "../pages/TopicPage";
import { AppShell } from "./AppShell";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/explore" element={<ExplorePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/library/recent" element={<RecentPage />} />
        <Route path="/library/favorites" element={<FavoritesPage />} />
        <Route path="/topics/:slug" element={<TopicPage />} />
        <Route path="/collections" element={<CollectionsPage />} />
        <Route path="/collections/:id" element={<CollectionDetailPage />} />
        <Route path="/clip/:id" element={<ClipDetailPage />} />
        <Route path="/watch/:id" element={<PlayerPage />} />
        <Route path="/downloads" element={<DownloadsPage />} />
        <Route
          path="/settings"
          element={
            <ComingSoon
              title="Settings"
              description="Capabilities, playback preferences, and diagnostics live here."
            />
          }
        />
      </Routes>
    </AppShell>
  );
}

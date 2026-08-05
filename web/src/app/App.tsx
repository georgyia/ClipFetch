import { Route, Routes } from "react-router-dom";
import { CommandPalette } from "../components/CommandPalette";
import { ShortcutsHelp } from "../components/ShortcutsHelp";
import { ToastProvider } from "../components/Toast";
import { useGlobalShortcuts } from "../lib/useGlobalShortcuts";
import { ClipDetailPage } from "../pages/ClipDetailPage";
import { CollectionDetailPage } from "../pages/CollectionDetailPage";
import { CollectionsPage } from "../pages/CollectionsPage";
import { DownloadsPage } from "../pages/DownloadsPage";
import { ExplorePage } from "../pages/ExplorePage";
import { FavoritesPage } from "../pages/FavoritesPage";
import { HomePage } from "../pages/HomePage";
import { LibraryPage } from "../pages/LibraryPage";
import { MissingMediaPage } from "../pages/MissingMediaPage";
import { PlayerPage } from "../pages/PlayerPage";
import { RecentPage } from "../pages/RecentPage";
import { SearchPage } from "../pages/SearchPage";
import { SettingsPage } from "../pages/SettingsPage";
import { TopicPage } from "../pages/TopicPage";
import { AppShell } from "./AppShell";
import { PageTransition } from "./PageTransition";

export function App() {
  useGlobalShortcuts();

  return (
    <ToastProvider>
      <ShortcutsHelp />
      <CommandPalette />
      <AppShell>
        <PageTransition>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/recent" element={<RecentPage />} />
            <Route path="/library/missing" element={<MissingMediaPage />} />
            <Route path="/library/favorites" element={<FavoritesPage />} />
            <Route path="/topics/:slug" element={<TopicPage />} />
            <Route path="/collections" element={<CollectionsPage />} />
            <Route path="/collections/:id" element={<CollectionDetailPage />} />
            <Route path="/clip/:id" element={<ClipDetailPage />} />
            <Route path="/watch/:id" element={<PlayerPage />} />
            <Route path="/downloads" element={<DownloadsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </PageTransition>
      </AppShell>
    </ToastProvider>
  );
}

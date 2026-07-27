/**
 * The app's icon vocabulary.
 *
 * Every icon in ClipFetch Watch comes from here, named for what it *means* rather than what it
 * draws — call sites say `Icons.favorite`, not `Heart`. That keeps one visual family across the
 * shell, cards, player, and forms, and makes swapping an individual glyph a one-line change.
 *
 * lucide is compiled to inline SVG at build time, so nothing is fetched at runtime: no icon font,
 * no CDN, CSP-safe on the loopback origin.
 */
import {
  ArrowRight,
  ArrowUpDown,
  Bookmark,
  Calendar,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock,
  Command,
  Compass,
  CornerDownLeft,
  Download,
  EllipsisVertical,
  ExternalLink,
  Eye,
  Film,
  Folder,
  FolderOpen,
  FolderPlus,
  Hash,
  Heart,
  House,
  Inbox,
  Keyboard,
  Layers,
  LibraryBig,
  ListVideo,
  LoaderCircle,
  type LucideIcon,
  Maximize,
  MessageCircle,
  Minimize,
  Monitor,
  Moon,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shuffle,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Trash2,
  TrendingUp,
  TriangleAlert,
  Volume2,
  VolumeX,
  X,
  Zap,
} from "lucide-react";

export type { LucideIcon };

export const Icons = {
  // Navigation
  home: House,
  explore: Compass,
  search: Search,
  library: LibraryBig,
  downloads: Download,
  settings: Settings,
  collections: Layers,
  topics: Hash,
  recent: Clock,

  // Playback
  play: Play,
  pause: Pause,
  next: SkipForward,
  previous: SkipBack,
  shuffle: Shuffle,
  queue: ListVideo,
  mute: VolumeX,
  unmute: Volume2,
  fullscreen: Maximize,
  exitFullscreen: Minimize,

  // Actions
  favorite: Heart,
  addToCollection: FolderPlus,
  bookmark: Bookmark,
  more: EllipsisVertical,
  add: Plus,
  remove: Trash2,
  refresh: RefreshCw,
  confirm: Check,
  close: X,
  openExternal: ExternalLink,
  filter: SlidersHorizontal,
  sort: ArrowUpDown,

  // Direction
  chevronLeft: ChevronLeft,
  chevronRight: ChevronRight,
  chevronDown: ChevronDown,
  arrowRight: ArrowRight,
  enter: CornerDownLeft,

  // Status & feedback
  spinner: LoaderCircle,
  warning: TriangleAlert,
  error: CircleAlert,
  empty: Inbox,
  sparkle: Sparkles,
  trending: TrendingUp,

  // Metadata
  views: Eye,
  comments: MessageCircle,
  published: Calendar,
  clip: Film,
  quality: Zap,

  // Files & system
  folder: Folder,
  folderOpen: FolderOpen,
  command: Command,
  keyboard: Keyboard,

  // Theme
  themeLight: Sun,
  themeDark: Moon,
  themeSystem: Monitor,
} as const;

export type IconName = keyof typeof Icons;

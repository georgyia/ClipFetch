# ClipFetch

[![CI](https://github.com/georgyia/ClipFetch/actions/workflows/ci.yml/badge.svg)](https://github.com/georgyia/ClipFetch/actions/workflows/ci.yml)

Download short-form videos from your feed to watch offline — straight from the terminal.

```
clipfetch -reels 25
```

That's it. ClipFetch opens a browser session, scrolls your Instagram Reels feed, grabs the
next 25 reels the feed serves you, and downloads them in parallel into a single folder —
ready to watch on a flight, on the train, or anywhere without a connection.

## Features

- **One command** — `clipfetch -reels N` downloads N reels from your personal Reels feed.
- **Fast** — reels are downloaded in parallel while the feed is still being scrolled.
- **Interactive** — live spinners and per-download progress bars in the terminal.
- **Self-contained** — no third-party downloader libraries; the extraction and download
  logic is built from scratch on top of a single dependency (Playwright, the browser driver).
- **Your session, your feed** — uses a dedicated local browser profile you sign in to once;
  no passwords stored, no cookie scraping from your real browser.

## Installation

Requires Python 3.9+.

```bash
pip install git+https://github.com/georgyia/ClipFetch.git
playwright install chromium
```

Or from a clone:

```bash
git clone https://github.com/georgyia/ClipFetch.git
cd ClipFetch
pip install -e .
playwright install chromium
```

## Usage

> **You must be signed in to Instagram first.** On the first run ClipFetch opens a browser
> window and asks you to sign in once. The session is stored in a local profile
> (`~/.clipfetch/profile`) and reused on every later run — no passwords are ever seen or
> stored by ClipFetch itself.

```bash
clipfetch -reels 25              # download the next 25 reels from your feed into ./reels/
clipfetch -reels 10 --out ~/clips  # choose the output folder
clipfetch -reels 5 --dry-run     # only list the video URLs, download nothing
clipfetch --help                 # all options
```

## How it works

1. Launches a Chromium instance with a persistent profile dedicated to ClipFetch.
2. Opens `instagram.com/reels/` and listens to the network responses the feed loads.
3. Collects direct video URLs from the feed API responses while auto-scrolling.
4. Streams the videos to disk in parallel worker threads as soon as each URL is found.

## Disclaimer

ClipFetch is intended for **personal use only** — downloading a handful of reels from your
own feed to watch them offline, exactly as you could in the app.

- Do **not** use it for mass scraping, re-uploading, or redistributing content.
- The videos you download belong to their creators; respect their rights.
- Automated access may violate [Instagram's Terms of Use](https://help.instagram.com/581066165581870).
  You use this tool at your own risk and are responsible for complying with the terms of
  the services you access and the laws that apply to you.
- This project is not affiliated with, endorsed by, or connected to Instagram/Meta.

## Contributing

Issues and pull requests are welcome — see the
[open tickets](https://github.com/georgyia/ClipFetch/issues) for planned features
(TikTok, YouTube Shorts, per-account downloads, and more).

## License

[MIT](LICENSE)

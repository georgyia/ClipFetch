"""Constants shared across ClipFetch modules."""

# Instagram serves a login wall to clients that advertise themselves as
# headless or unknown, so both the headless browser and the plain-HTTP
# downloader present themselves as a regular desktop Chrome.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

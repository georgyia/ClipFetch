"""Allow running as ``python -m clipfetch``."""

from clipfetch.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

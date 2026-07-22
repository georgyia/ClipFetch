"""ClipFetch Watch HTTP API (FastAPI).

Imported only by the web command and its tests, so the base install stays Playwright-only.
Everything here lives beneath ``/api/v1`` except health probes and OpenAPI docs, and it talks to the
rest of ClipFetch exclusively through the service layer (ADR 0001).
"""

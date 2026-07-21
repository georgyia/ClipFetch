"""Reusable service layer shared by the ClipFetch CLI and the ClipFetch Watch API.

Services take validated domain values and return typed results or public contracts. They never
import FastAPI or any frontend concept, and they never accept argparse namespaces — the boundary
rules in `docs/adr/0001-monorepo-and-runtime-boundaries.md`.
"""

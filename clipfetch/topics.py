"""Library-scoped topic definitions and local multi-label categorization."""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clipfetch.catalog import Catalog, CatalogError, TopicAssignment
from clipfetch.semantic import Embedder, semantic_document, semantic_index

TOPICS_FILE = ".clipfetch/topics.json"
TOPICS_SCHEMA_VERSION = 1
DEFAULT_THRESHOLD = 0.42
_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TopicError(RuntimeError):
    """Topic definitions or assignments are invalid/unavailable."""


@dataclass(frozen=True)
class TopicDefinition:
    name: str
    description: str
    examples: tuple[str, ...]

    def document(self) -> str:
        return f"topic: {self.name}\ndescription: {self.description}\nexamples: " + " | ".join(
            self.examples
        )


@dataclass(frozen=True)
class TopicConfig:
    threshold: float
    topics: tuple[TopicDefinition, ...]


@dataclass(frozen=True)
class CategorizeReport:
    scanned: int
    categorized: int
    unchanged: int
    uncategorized: int


STARTER_TOPICS = (
    TopicDefinition(
        "entrepreneurship",
        "founding and growing companies",
        ("startup fundraising", "customer acquisition for founders"),
    ),
    TopicDefinition(
        "business",
        "operating companies and professional strategy",
        ("business operations", "company leadership"),
    ),
    TopicDefinition(
        "finance",
        "money, investing, markets and personal budgeting",
        ("personal budget", "stock market investing"),
    ),
    TopicDefinition(
        "technology",
        "software, hardware, science and digital products",
        ("artificial intelligence", "software engineering"),
    ),
    TopicDefinition(
        "marketing",
        "promotion, branding, sales and audience growth",
        ("social media campaign", "brand positioning"),
    ),
    TopicDefinition(
        "education", "learning, teaching and study skills", ("language lesson", "how to study")
    ),
    TopicDefinition(
        "health-and-fitness",
        "physical health, exercise and wellbeing",
        ("strength workout", "healthy habits"),
    ),
    TopicDefinition(
        "food",
        "cooking, recipes, ingredients and restaurants",
        ("easy pasta recipe", "restaurant review"),
    ),
    TopicDefinition(
        "travel",
        "destinations, journeys and local experiences",
        ("city travel guide", "things to do abroad"),
    ),
    TopicDefinition(
        "entertainment",
        "film, music, games, comedy and celebrities",
        ("movie review", "funny sketch"),
    ),
    TopicDefinition(
        "news", "current events and public affairs", ("breaking news report", "election update")
    ),
)


def topics_path(root: Path) -> Path:
    return root.resolve() / TOPICS_FILE


def init_topics(root: Path, *, force: bool = False) -> TopicConfig:
    path = topics_path(root)
    if path.exists() and not force:
        return load_topics(root)
    config = TopicConfig(DEFAULT_THRESHOLD, STARTER_TOPICS)
    save_topics(root, config)
    return config


def load_topics(root: Path) -> TopicConfig:
    path = topics_path(root)
    if not path.exists():
        raise TopicError(f"topics are not initialized; run: clipfetch topics init {root}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as err:
        raise TopicError(f"invalid topics file {path}: {err}") from err
    if not isinstance(value, dict):
        raise TopicError(f"invalid topics file {path}: expected an object")
    version = value.get("schema_version", 0)
    if version not in (0, TOPICS_SCHEMA_VERSION):
        raise TopicError(f"unsupported topics schema version: {version}")
    threshold = value.get("threshold", DEFAULT_THRESHOLD)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise TopicError("topic threshold must be a number")
    if not 0 <= float(threshold) <= 1:
        raise TopicError("topic threshold must be between 0 and 1")
    raw_topics = value.get("topics")
    if not isinstance(raw_topics, list):
        raise TopicError("topics must be a list")
    topics = tuple(_definition(item) for item in raw_topics)
    names = [topic.name for topic in topics]
    if len(names) != len(set(names)):
        raise TopicError("duplicate topic names are not allowed")
    return TopicConfig(float(threshold), topics)


def save_topics(root: Path, config: TopicConfig) -> None:
    path = topics_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": TOPICS_SCHEMA_VERSION,
        "threshold": config.threshold,
        "topics": [
            {
                "name": topic.name,
                "description": topic.description,
                "examples": list(topic.examples),
            }
            for topic in config.topics
        ],
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def add_topic(root: Path, name: str, description: str, examples: Sequence[str]) -> TopicDefinition:
    config = load_topics(root)
    normalized = normalize_topic_name(name)
    if any(topic.name == normalized for topic in config.topics):
        raise TopicError(f"topic already exists: {normalized}")
    definition = _definition(
        {"name": normalized, "description": description, "examples": list(examples)}
    )
    save_topics(root, TopicConfig(config.threshold, (*config.topics, definition)))
    return definition


def remove_topic(root: Path, name: str) -> None:
    config = load_topics(root)
    normalized = normalize_topic_name(name)
    remaining = tuple(topic for topic in config.topics if topic.name != normalized)
    if len(remaining) == len(config.topics):
        raise TopicError(f"unknown topic: {normalized}")
    save_topics(root, TopicConfig(config.threshold, remaining))
    with Catalog.open(root) as catalog:
        catalog.remove_topic(normalized)


def normalize_topic_name(value: str) -> str:
    name = value.strip().casefold()
    if not _NAME.fullmatch(name):
        raise TopicError("topic names must use lowercase letters, numbers, and single hyphens")
    return name


def categorize_library(root: Path, embedder: Embedder) -> CategorizeReport:
    config = load_topics(root)
    if not config.topics:
        raise TopicError("no topic definitions are configured")
    semantic_index(root, embedder)
    definition_hash = _config_hash(config)
    topic_vectors = _vectors(embedder, [topic.document() for topic in config.topics])
    categorized = unchanged = uncategorized = 0
    with Catalog.open(root) as catalog:
        records = [
            record
            for record in catalog.all()
            if record.available and (root / record.relative_path).is_file()
        ]
        embeddings = {
            (item.platform, item.clip_id): item
            for item in catalog.embeddings_for(embedder.model_id, embedder.revision)
        }
        for record in records:
            document = semantic_document(record)
            if not document:
                continue
            input_hash = hashlib.sha256(document.encode("utf-8")).hexdigest()
            existing = [
                item
                for item in catalog.topic_assignments(record.platform, record.clip_id)
                if item.provenance == "model"
            ]
            if existing and all(
                item.definition_hash == definition_hash
                and item.input_hash == input_hash
                and item.model_id == embedder.model_id
                and item.model_revision == embedder.revision
                and item.threshold == config.threshold
                for item in existing
            ):
                unchanged += 1
                uncategorized += int(existing[0].topic == "uncategorized")
                continue
            embedding = embeddings.get((record.platform, record.clip_id))
            if not embedding or embedding.input_hash != input_hash:
                continue
            clip_vector = _unpack(embedding.vector, embedding.dimension)
            scores = sorted(
                (
                    (sum(left * right for left, right in zip(clip_vector, vector)), topic.name)
                    for topic, vector in zip(config.topics, topic_vectors)
                    if len(vector) == embedding.dimension
                ),
                key=lambda item: (-item[0], item[1]),
            )
            manual = {
                item.topic
                for item in catalog.topic_assignments(record.platform, record.clip_id)
                if item.provenance == "manual"
            }
            selected = [
                item for item in scores if item[0] >= config.threshold and item[1] not in manual
            ][:3]
            now = datetime.now(timezone.utc).isoformat()
            if not selected and not manual:
                selected = [(0.0, "uncategorized")]
                uncategorized += 1
            assignments = [
                TopicAssignment(
                    record.platform,
                    record.clip_id,
                    topic,
                    score,
                    "model",
                    embedder.model_id,
                    embedder.revision,
                    definition_hash,
                    input_hash,
                    config.threshold,
                    now,
                )
                for score, topic in selected
            ]
            catalog.replace_model_topics(record.platform, record.clip_id, assignments)
            categorized += 1
    return CategorizeReport(len(records), categorized, unchanged, uncategorized)


def tag_clip(root: Path, clip_id: str, topic: str, *, remove: bool = False) -> None:
    config = load_topics(root)
    normalized = normalize_topic_name(topic)
    if normalized not in {item.name for item in config.topics}:
        raise TopicError(f"unknown topic: {normalized}")
    with Catalog.open(root) as catalog:
        matches = [record for record in catalog.all() if record.clip_id == clip_id]
        if len(matches) != 1:
            raise CatalogError(
                f"clip id {'not found' if not matches else 'is ambiguous'}: {clip_id}"
            )
        record = matches[0]
        if remove:
            catalog.remove_manual_topic(record.platform, record.clip_id, normalized)
        else:
            catalog.set_manual_topic(record.platform, record.clip_id, normalized)


def assignment_details(root: Path, platform: str, clip_id: str) -> list[dict[str, Any]]:
    config = load_topics(root)
    descriptions = {topic.name: topic.description for topic in config.topics}
    with Catalog.open(root) as catalog:
        assignments = catalog.topic_assignments(platform, clip_id)
    return [
        {
            "topic": item.topic,
            "description": descriptions.get(item.topic),
            "confidence": item.confidence,
            "provenance": item.provenance,
            "model_id": item.model_id,
            "model_revision": item.model_revision,
        }
        for item in assignments
    ]


def _definition(value: Any) -> TopicDefinition:
    if not isinstance(value, dict):
        raise TopicError("each topic must be an object")
    name = normalize_topic_name(str(value.get("name", "")))
    description = value.get("description")
    examples = value.get("examples")
    if not isinstance(description, str) or not description.strip():
        raise TopicError(f"topic {name!r} requires a description")
    if (
        not isinstance(examples, list)
        or not examples
        or not all(isinstance(item, str) and item.strip() for item in examples)
    ):
        raise TopicError(f"topic {name!r} requires one or more example phrases")
    return TopicDefinition(name, description.strip(), tuple(item.strip() for item in examples))


def _config_hash(config: TopicConfig) -> str:
    payload = json.dumps(
        [(topic.name, topic.description, topic.examples) for topic in config.topics],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _vectors(embedder: Embedder, texts: Sequence[str]) -> list[tuple[float, ...]]:
    vectors = list(embedder.embed(texts))
    if len(vectors) != len(texts):
        raise TopicError("embedder returned an incomplete topic batch")
    return [_normalize(vector) for vector in vectors]


def _normalize(values: Sequence[float]) -> tuple[float, ...]:
    vector = tuple(float(value) for value in values)
    norm = math.sqrt(sum(value * value for value in vector))
    if not vector or not math.isfinite(norm) or norm == 0:
        raise TopicError("embedder returned an invalid topic vector")
    return tuple(value / norm for value in vector)


def _unpack(value: bytes, dimension: int) -> tuple[float, ...]:
    if len(value) != dimension * 4:
        raise TopicError("stored clip embedding is corrupt")
    return struct.unpack(f"<{dimension}f", value)

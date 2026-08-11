from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

from pydantic import ValidationError

from server.knowledge_retrieval.errors import KnowledgeIndexError
from server.knowledge_retrieval.index_schemas import IndexManifest, VectorRecord
from server.knowledge_retrieval.manifest import canonical_json, sha256_json


INDEX_SCHEMA_VERSION = "1.0.0"
VECTOR_STORE_NAME = "exact_cosine_v1"
QDRANT_VECTOR_STORE_NAME = "qdrant_dense_v1"
SUPPORTED_VECTOR_STORE_NAMES = frozenset(
    {VECTOR_STORE_NAME, QDRANT_VECTOR_STORE_NAME}
)
DISTANCE_METRIC = "cosine"
INDEX_MANIFEST_FILENAME = "index-manifest.json"


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise KnowledgeIndexError("Cannot read the corpus manifest.") from exc


def vector_sha256(vector: list[float]) -> str:
    digest = hashlib.sha256()
    for value in vector:
        digest.update(struct.pack("!d", float(value)))
    return digest.hexdigest()


def index_identity_payload(
    *,
    corpus_root_hash: str,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimensions: int,
    vector_store: str = VECTOR_STORE_NAME,
    schema_version: str = INDEX_SCHEMA_VERSION,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "corpus_root_hash": corpus_root_hash,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "vector_store": vector_store,
    }


def calculate_index_id(**values: object) -> str:
    return f"knowledge-{sha256_json(values)[:24]}"


def index_root_payload(manifest: IndexManifest) -> dict[str, object]:
    return {
        **index_identity_payload(
            corpus_root_hash=manifest.corpus_root_hash,
            embedding_provider=manifest.embedding_provider,
            embedding_model=manifest.embedding_model,
            embedding_dimensions=manifest.embedding_dimensions,
            vector_store=manifest.vector_store,
            schema_version=manifest.schema_version,
        ),
        "distance_metric": manifest.distance_metric,
        "chunks": [
            {
                "chunk_id": chunk_id,
                "content_sha256": manifest.chunk_content_hashes[chunk_id],
                "vector_sha256": manifest.vector_hashes[chunk_id],
            }
            for chunk_id in sorted(manifest.chunk_ids)
        ],
    }


def calculate_index_root_hash(manifest: IndexManifest) -> str:
    return sha256_json(index_root_payload(manifest))


def build_index_manifest(
    *,
    corpus_root_hash: str,
    corpus_manifest_sha256: str,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimensions: int,
    embedding_normalized: bool,
    records: list[VectorRecord],
    warnings: list[str],
    vector_store: str = VECTOR_STORE_NAME,
    created_at: datetime | None = None,
) -> IndexManifest:
    ordered = sorted(records, key=lambda item: item.chunk_id)
    identity = index_identity_payload(
        corpus_root_hash=corpus_root_hash,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        vector_store=vector_store,
    )
    draft = IndexManifest(
        schema_version=INDEX_SCHEMA_VERSION,
        index_id=calculate_index_id(**identity),
        corpus_root_hash=corpus_root_hash,
        corpus_manifest_sha256=corpus_manifest_sha256,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        embedding_normalized=embedding_normalized,
        vector_store=vector_store,
        distance_metric=DISTANCE_METRIC,
        chunk_count=len(ordered),
        chunk_ids=[record.chunk_id for record in ordered],
        chunk_content_hashes={
            record.chunk_id: record.content_sha256 for record in ordered
        },
        vector_hashes={
            record.chunk_id: vector_sha256(record.vector) for record in ordered
        },
        created_at=created_at or datetime.now(timezone.utc),
        root_hash="0" * 64,
        warnings=sorted(set(warnings)),
    )
    return draft.model_copy(update={"root_hash": calculate_index_root_hash(draft)})


def write_index_manifest(path: Path, manifest: IndexManifest) -> None:
    payload = (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    try:
        path.write_text(payload, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise KnowledgeIndexError("Failed to write the index manifest.") from exc


def load_index_manifest(path: Path) -> IndexManifest:
    try:
        return IndexManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise KnowledgeIndexError("Index manifest is missing or invalid.") from exc


def validate_index_manifest(manifest: IndexManifest) -> None:
    if calculate_index_root_hash(manifest) != manifest.root_hash:
        raise KnowledgeIndexError("Index manifest root hash is invalid.")
    expected_id = calculate_index_id(
        **index_identity_payload(
            corpus_root_hash=manifest.corpus_root_hash,
            embedding_provider=manifest.embedding_provider,
            embedding_model=manifest.embedding_model,
            embedding_dimensions=manifest.embedding_dimensions,
            vector_store=manifest.vector_store,
            schema_version=manifest.schema_version,
        )
    )
    if manifest.index_id != expected_id:
        raise KnowledgeIndexError("Index manifest identity is invalid.")
    if (
        manifest.vector_store not in SUPPORTED_VECTOR_STORE_NAMES
        or manifest.distance_metric != DISTANCE_METRIC
    ):
        raise KnowledgeIndexError("Index manifest store configuration is unsupported.")
    serialized = canonical_json(manifest.model_dump(mode="json"))
    lowered = serialized.lower()
    if "api_key" in lowered or "authorization" in lowered:
        raise KnowledgeIndexError("Index manifest contains a forbidden secret field.")
    if re_absolute_path(serialized):
        raise KnowledgeIndexError("Index manifest contains an absolute path.")


def re_absolute_path(value: str) -> bool:
    return bool(
        __import__("re").search(r"(?i)(?:[A-Z]:\\\\|/(?:home|Users|var/tmp)/)", value)
    )

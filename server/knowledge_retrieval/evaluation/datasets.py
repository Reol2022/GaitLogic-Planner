from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.evaluation.schemas import (
    RagAnswerDataset,
    RetrievalDataset,
)

DatasetT = TypeVar("DatasetT", bound=BaseModel)


class EvaluationDatasetError(ValueError):
    pass


def canonical_dataset_hash(payload: dict[str, object]) -> str:
    hash_payload = {key: value for key, value in payload.items() if key != "content_sha256"}
    encoded = json.dumps(
        hash_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path, model: type[DatasetT]) -> DatasetT:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationDatasetError(f"Cannot load evaluation dataset: {path}") from exc
    expected = canonical_dataset_hash(payload)
    if payload.get("content_sha256") != expected:
        raise EvaluationDatasetError("Evaluation dataset SHA-256 does not match content")
    try:
        dataset = model.model_validate(payload)
    except ValidationError as exc:
        raise EvaluationDatasetError(str(exc)) from exc
    case_ids = [case.case_id for case in dataset.cases]
    if len(case_ids) != len(set(case_ids)):
        raise EvaluationDatasetError("Evaluation case IDs must be unique")
    return dataset


def load_retrieval_dataset(
    path: Path,
    *,
    corpus_manifest_path: Path = Path("knowledge/manifests/corpus-v1.json"),
) -> RetrievalDataset:
    dataset = _load(path, RetrievalDataset)
    corpus = load_manifest(corpus_manifest_path)
    document_ids = {item.document_id for item in corpus.documents}
    chunk_ids = {item.chunk_id for item in corpus.chunks}
    for case in dataset.cases:
        referenced = {
            item.document_id for item in case.relevant_documents
        } | set(case.forbidden_document_ids)
        missing_documents = referenced - document_ids
        if missing_documents:
            raise EvaluationDatasetError(
                f"{case.case_id} references missing documents: {sorted(missing_documents)}"
            )
        missing_chunks = set(case.acceptable_chunk_ids) - chunk_ids
        if missing_chunks:
            raise EvaluationDatasetError(
                f"{case.case_id} references missing chunks: {sorted(missing_chunks)}"
            )
    return dataset


def load_rag_dataset(path: Path) -> RagAnswerDataset:
    return _load(path, RagAnswerDataset)

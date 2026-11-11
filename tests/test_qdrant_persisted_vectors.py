"""Synthetic network-storage float32 regression; no remote credentials needed."""
import struct

import pytest

from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider
from server.knowledge_retrieval.errors import KnowledgeIndexError
from server.knowledge_retrieval.index_manifest import vector_sha256
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.vector_stores.exact_cosine import ExactCosineVectorStore
from tests.knowledge_index_helpers import prepare_repository, vector_record


def float32(value):
    return struct.unpack("!f", struct.pack("!f", value))[0]


class NetworkFloat32Store(ExactCosineVectorStore):
    def build(self, records):
        super().build([
            record.model_copy(update={"vector": [float32(v) for v in record.vector]})
            for record in records
        ])


def test_float32_roundtrip_needs_persisted_hash():
    record = vector_record(vector=[0.123456789, 0.987654321])
    persisted = record.model_copy(update={"vector": [float32(v) for v in record.vector]})
    assert vector_sha256(record.vector) != vector_sha256(persisted.vector)
    KnowledgeIndexService._check_persisted_records([record], [persisted])


def test_qdrant_build_seals_persisted_vectors_and_still_rejects_tampering(tmp_path, monkeypatch):
    prepare_repository(tmp_path)
    service = KnowledgeIndexService(repository_root=tmp_path, vector_store="qdrant")
    monkeypatch.setattr(service, "_store", lambda directory, **kwargs: NetworkFloat32Store(
        directory, expected_dimensions=kwargs["dimensions"]
    ))
    result = service.build(DeterministicEmbeddingProvider(dimensions=16))
    assert service.validate(result.manifest.index_id).root_hash == result.manifest.root_hash
    directory = service.index_root / result.manifest.index_id
    store = NetworkFloat32Store(directory, expected_dimensions=16)
    records = store.records()
    records[0].vector[0] += 0.01
    # Explicit fixture tamper, not a production mutation.
    store.path.unlink()
    store.build(records)
    with pytest.raises(KnowledgeIndexError, match="vector hash"):
        service.validate(result.manifest.index_id)


@pytest.mark.parametrize("change", ["metadata", "vector", "missing", "duplicate", "identity"])
def test_persisted_storage_changes_are_not_silently_accepted(change):
    original = vector_record()
    stored = original.model_copy(deep=True)
    records = [stored]
    if change == "metadata":
        stored.source_id = "different-source"
    elif change == "vector":
        stored.vector[0] += 0.01
    elif change == "missing":
        records = []
    elif change == "duplicate":
        records = [stored, stored]
    else:
        stored.chunk_id = "other-id"
    with pytest.raises(KnowledgeIndexError):
        KnowledgeIndexService._check_persisted_records([original], records)

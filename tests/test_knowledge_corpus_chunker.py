from __future__ import annotations

from pathlib import Path

from server.knowledge_retrieval.chunker import DeterministicKnowledgeChunker
from server.knowledge_retrieval.loader import KnowledgeCorpusLoader
from server.knowledge_retrieval.paths import CorpusPaths
from tests.knowledge_corpus_helpers import SECTIONS, write_corpus


def _document(tmp_path: Path, body: str):
    root = write_corpus(tmp_path, body=body)
    loader = KnowledgeCorpusLoader(
        CorpusPaths.create(root, repository_root=tmp_path)
    )
    return loader.load()[0][0]


def test_heading_chunks_have_stable_ids_and_hashes(tmp_path: Path) -> None:
    document = _document(tmp_path, SECTIONS)
    chunker = DeterministicKnowledgeChunker(max_chars=300)
    first = chunker.chunk_document(document)
    second = chunker.chunk_document(document)
    assert [item.chunk_id for item in first] == [
        item.chunk_id for item in second
    ]
    assert [item.content_sha256 for item in first] == [
        item.content_sha256 for item in second
    ]
    assert first[0].chunk_id.endswith("#applicable-scenarios#001")
    assert all("---" not in item.content for item in first)


def test_long_paragraph_splits_at_sentence_boundaries(tmp_path: Path) -> None:
    paragraph = "第一句用于测试。" * 80
    body = SECTIONS.replace("适用于虚构测试场景。", paragraph)
    chunks = DeterministicKnowledgeChunker(max_chars=240).chunk_document(
        _document(tmp_path, body)
    )
    applicable = [
        item for item in chunks if item.section == "适用场景"
    ]
    assert len(applicable) > 1
    assert all(item.content.rstrip().endswith("。") for item in applicable)


def test_lists_code_blocks_and_tables_remain_intact(tmp_path: Path) -> None:
    list_block = "\n".join(f"- 列表项目 {index}" for index in range(50))
    code_block = "```text\n" + ("example-line\n" * 80) + "```"
    table_block = "| 项目 | 说明 |\n| --- | --- |\n" + "\n".join(
        f"| {index} | 示例内容 |" for index in range(40)
    )
    body = SECTIONS.replace(
        "- 训练数据存在。\n- 数据质量可用。",
        list_block,
    ).replace(
        "采用保守、可复核的建议。",
        code_block,
    ).replace(
        "不构成医疗建议。",
        table_block,
    )
    chunks = DeterministicKnowledgeChunker(max_chars=240).chunk_document(
        _document(tmp_path, body)
    )
    combined = "\n".join(item.content for item in chunks)
    assert list_block in combined
    assert code_block in combined
    assert table_block in combined


def test_estimated_tokens_are_stable_approximations(tmp_path: Path) -> None:
    chunks = DeterministicKnowledgeChunker().chunk_document(
        _document(tmp_path, SECTIONS)
    )
    assert all(item.estimated_token_count > 0 for item in chunks)
    assert all(item.metadata.document_path == "documents/document.md" for item in chunks)

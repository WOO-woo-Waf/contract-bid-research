from pathlib import Path

import httpx

from contract_bid_research.config import ModelAPISettings
from contract_bid_research.document.builder import CanonicalDocumentBuilder
from contract_bid_research.document.models import ParseMetadata
from contract_bid_research.knowledge.model_api import ModelAPIClient
from contract_bid_research.knowledge.models import RerankResult
from contract_bid_research.knowledge.gbrain import GBrainAdapter
from contract_bid_research.knowledge.projection import GBrainProjectionBuilder
from contract_bid_research.knowledge.sqlite_index import SQLiteKnowledgeIndex, lexical_terms


def model_settings() -> ModelAPISettings:
    return ModelAPISettings(
        base_url="https://model.example/v1",
        api_key="sk-test",
        timeout_s=10,
        embedding_model="text-embedding-v3",
        embedding_dimensions=3,
        rerank_model="qwen3-rerank",
        chat_model="qwen-plus",
    )


def test_model_client_validates_embeddings_and_rerank() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/embeddings":
            return httpx.Response(
                200,
                json={"data": [{"index": 0, "embedding": [1, 0, 0]}, {"index": 1, "embedding": [0, 1, 0]}]},
            )
        if request.url.path == "/v1/rerank":
            return httpx.Response(200, json={"results": [{"index": 1, "relevance_score": 0.9}]})
        return httpx.Response(404)

    with ModelAPIClient(model_settings(), transport=httpx.MockTransport(handler)) as client:
        assert client.embed(["a", "b"]) == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        assert client.rerank("q", ["a", "b"], top_n=1)[0].index == 1


class FakeModelClient:
    dimensions = 3

    def embed(self, texts):
        vectors = []
        for text in texts:
            if "锚点" in text or "位置" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "索引" in text or "检索" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    def rerank(self, query, documents, top_n=None):
        scored = [RerankResult(index=index, relevance_score=1.0 if "锚点" in text else 0.1) for index, text in enumerate(documents)]
        return sorted(scored, key=lambda item: item.relevance_score, reverse=True)[: top_n or len(scored)]


def sample_document(tmp_path: Path):
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    return CanonicalDocumentBuilder(chunk_chars=200).build(
        source_path=source,
        markdown="# 文档基础设施",
        content_list=[
            {"type": "text", "text": "来源锚点使用页码和边界框定位。", "page_idx": 2, "bbox": [1, 2, 3, 4]},
            {"type": "text", "text": "知识索引支持关键词和向量混合检索。", "page_idx": 3, "bbox": [1, 2, 3, 4]},
        ],
        parse=ParseMetadata(parser_version="3.4.4"),
    )


def test_sqlite_index_returns_evidence_and_cjk_keyword_search(tmp_path: Path) -> None:
    document = sample_document(tmp_path)
    with SQLiteKnowledgeIndex(tmp_path / "knowledge.sqlite3", FakeModelClient()) as index:
        assert index.index_document(document) == len(document.chunks)
        hits = index.search("原始位置锚点", mode="hybrid", limit=1, rerank=True)
        keyword_hits = index.search("混合检索", mode="keyword", limit=2, rerank=False)

    assert hits[0].node_ids
    assert hits[0].anchors[0].page_index == 2
    assert hits[0].retrieval_mode == "rerank"
    assert keyword_hits
    assert "混合检索" in keyword_hits[0].text
    assert "混合" in lexical_terms("混合检索")


def test_gbrain_projection_contains_provenance_and_links(tmp_path: Path) -> None:
    document = sample_document(tmp_path)
    manifest = GBrainProjectionBuilder(tmp_path / "projection").build(document)

    assert len(manifest.page_paths) == len(document.chunks) + 1
    assert len(manifest.links) == len(document.chunks)
    chunk_page = manifest.page_paths[1].read_text(encoding="utf-8")
    assert "canonical_node_ids" in chunk_page
    assert f"[[{manifest.document_slug}" in chunk_page


class FakeGBrainAdapter(GBrainAdapter):
    def __init__(self, search_rows=None, graph_rows=None):
        self.search_rows = search_rows or []
        self.graph_rows = graph_rows or []

    def hybrid_search(self, query: str, *, limit: int = 10):
        return self.search_rows[:limit]

    def call(self, operation: str, parameters: dict):
        assert operation == "traverse_graph"
        return self.graph_rows


def test_gbrain_hits_map_back_to_canonical_evidence(tmp_path: Path) -> None:
    document = sample_document(tmp_path)
    chunk = document.chunks[0]
    adapter = FakeGBrainAdapter(
        search_rows=[
            {"slug": f"documents/{document.canonical_document_id}", "score": 0.99},
            {
                "slug": f"documents/{document.canonical_document_id}/chunks/{chunk.chunk_id}",
                "score": 0.88,
            },
        ]
    )

    hits = adapter.evidence_search("来源位置", {document.canonical_document_id: document}, limit=1)

    assert hits[0].chunk_id == chunk.chunk_id
    assert hits[0].anchors == chunk.anchors


def test_gbrain_graph_deduplicates_depth_repeats() -> None:
    edge = {"from_slug": "chunks/a", "to_slug": "documents/d", "link_type": "derived_from"}
    adapter = FakeGBrainAdapter(graph_rows=[{**edge, "depth": 2}, {**edge, "depth": 1}])

    graph = adapter.graph("documents/d", depth=2)

    assert graph == [{**edge, "depth": 1}]

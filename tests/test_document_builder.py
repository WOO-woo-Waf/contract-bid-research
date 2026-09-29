from pathlib import Path

from contract_bid_research.document.builder import CanonicalDocumentBuilder
from contract_bid_research.document.models import ParseMetadata


def test_builder_produces_stable_nodes_chunks_and_anchors(tmp_path: Path) -> None:
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"deterministic source")
    content_list = [
        {"type": "title", "text": "基础设施说明", "page_idx": 0, "bbox": [10, 20, 900, 80]},
        {"type": "text", "text": "使用页码和边界框定位原始证据。", "page_idx": 0, "bbox": [10, 100, 900, 180]},
        {"type": "text", "text": "知识索引是可重建的派生数据。", "page_idx": 1, "bbox": [10, 20, 900, 100]},
    ]
    parse = ParseMetadata(parser_version="3.4.4", backend="vlm-engine", task_id="task-1")
    builder = CanonicalDocumentBuilder(chunk_chars=200)

    first = builder.build(source_path=source, markdown="# 基础设施说明", content_list=content_list, parse=parse)
    second = builder.build(source_path=source, markdown="# 基础设施说明", content_list=content_list, parse=parse)

    assert first.canonical_document_id == second.canonical_document_id
    assert [node.node_id for node in first.nodes] == [node.node_id for node in second.nodes]
    assert len(first.nodes) == 3
    assert first.nodes[0].source_anchor.kind == "page_bbox"
    assert first.nodes[0].source_anchor.coordinate_space == "bbox_1000"
    assert first.quality["anchor_coverage"] == 1.0
    assert first.chunks[0].node_ids


def test_builder_falls_back_to_markdown_when_content_list_is_empty(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    source.write_bytes(b"office")

    document = CanonicalDocumentBuilder().build(
        source_path=source,
        markdown="第一段。\n\n第二段。",
        content_list=[],
        parse=ParseMetadata(parser_version="3.4.4"),
    )

    assert len(document.nodes) == 2
    assert "content_list_empty:used_markdown_fallback" in document.warnings

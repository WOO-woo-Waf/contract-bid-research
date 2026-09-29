"""Deterministic MinerU content-list to Canonical Document conversion."""

from __future__ import annotations

import mimetypes
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .ids import sha256_bytes, sha256_file, stable_id
from .models import (
    Asset,
    CanonicalDocument,
    DocumentChunk,
    DocumentNode,
    ParseMetadata,
    SourceAnchor,
    SourceFile,
)

_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def _flatten(items: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for item in items:
        if isinstance(item, dict):
            yield item
            for key in ("children", "items", "blocks", "body"):
                nested = item.get(key)
                if isinstance(nested, list):
                    yield from _flatten(nested)
        elif isinstance(item, list):
            yield from _flatten(item)


def _first_text(item: dict[str, Any]) -> str:
    for key in ("text", "content", "table_body", "caption", "title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            joined = "\n".join(str(part) for part in value if part)
            if joined.strip():
                return joined.strip()
    return ""


def _anchor(item: dict[str, Any], raw_path: str) -> SourceAnchor:
    page_raw = item.get("page_idx", item.get("page_index"))
    page_index = page_raw if isinstance(page_raw, int) and page_raw >= 0 else None
    bbox_raw = item.get("bbox")
    bbox: tuple[float, float, float, float] | None = None
    if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) >= 4:
        try:
            candidate = tuple(float(value) for value in bbox_raw[:4])
            if candidate[2] >= candidate[0] and candidate[3] >= candidate[1]:
                bbox = candidate  # type: ignore[assignment]
        except (TypeError, ValueError):
            bbox = None
    if bbox is not None:
        coordinate_space = "bbox_1000" if max(bbox) <= 1000 else "parser_native"
        return SourceAnchor(
            kind="page_bbox",
            page_index=page_index,
            bbox=bbox,
            coordinate_space=coordinate_space,
            raw_path=raw_path,
        )
    if page_index is not None:
        return SourceAnchor(kind="page", page_index=page_index, raw_path=raw_path)
    return SourceAnchor(kind="unknown", raw_path=raw_path)


class CanonicalDocumentBuilder:
    """Build stable document data without adding contract/tender semantics."""

    def __init__(self, *, chunk_chars: int = 1200) -> None:
        if chunk_chars < 200:
            raise ValueError("chunk_chars must be at least 200")
        self.chunk_chars = chunk_chars

    def build(
        self,
        *,
        source_path: Path,
        markdown: str,
        content_list: list[Any],
        parse: ParseMetadata,
        assets: Iterable[Asset] = (),
    ) -> CanonicalDocument:
        source_path = source_path.resolve()
        source_hash = sha256_file(source_path)
        normalized_content = json.dumps(content_list, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        canonical_id = stable_id(
            "doc",
            source_hash,
            parse.parser,
            parse.parser_version,
            parse.backend,
            parse.artifact_hashes,
            sha256_bytes(markdown.encode("utf-8")),
            sha256_bytes(normalized_content.encode("utf-8")),
            "canonical-builder-v1",
        )
        asset_list = tuple(assets)
        asset_by_path = {asset.relative_path: asset.asset_id for asset in asset_list}

        nodes: list[DocumentNode] = []
        warnings: list[str] = []
        for order, item in enumerate(_flatten(content_list)):
            node_type = str(item.get("type") or item.get("block_type") or "unknown")
            text = _first_text(item)
            raw_path = f"content_list[{order}]"
            anchor = _anchor(item, raw_path)
            refs: list[str] = []
            for key in ("img_path", "image_path", "asset_path"):
                value = item.get(key)
                if isinstance(value, str):
                    matched = asset_by_path.get(value) or asset_by_path.get(value.lstrip("./"))
                    if matched:
                        refs.append(matched)
            if not text and not refs and node_type not in {"page", "page_header", "page_footer"}:
                warnings.append(f"empty_node:{order}:{node_type}")
            node_id = stable_id(
                "node", canonical_id, order, node_type, normalize_text(text), anchor.model_dump(mode="json")
            )
            nodes.append(
                DocumentNode(
                    node_id=node_id,
                    type=node_type,
                    order=order,
                    text=text,
                    normalized_text=normalize_text(text),
                    source_anchor=anchor,
                    asset_refs=tuple(refs),
                    confidence=float(item["score"])
                    if isinstance(item.get("score"), (int, float)) and 0 <= float(item["score"]) <= 1
                    else None,
                    provenance={"raw_type": node_type, "raw_path": raw_path},
                )
            )

        if not nodes and markdown.strip():
            for order, paragraph in enumerate(part for part in markdown.split("\n\n") if part.strip()):
                normalized = normalize_text(paragraph)
                nodes.append(
                    DocumentNode(
                        node_id=stable_id("node", canonical_id, order, "markdown", normalized),
                        type="markdown_paragraph",
                        order=order,
                        text=paragraph.strip(),
                        normalized_text=normalized,
                        source_anchor=SourceAnchor(kind="unknown", raw_path=f"markdown[{order}]"),
                    )
                )
            warnings.append("content_list_empty:used_markdown_fallback")

        chunks = self._chunks(canonical_id, nodes)
        anchor_count = sum(node.source_anchor.kind in {"page", "page_bbox"} for node in nodes)
        source = SourceFile(
            file_name=source_path.name,
            media_type=mimetypes.guess_type(source_path.name)[0] or "application/octet-stream",
            sha256=source_hash,
            size_bytes=source_path.stat().st_size,
        )
        return CanonicalDocument(
            canonical_document_id=canonical_id,
            source=source,
            parse=parse,
            markdown=markdown,
            nodes=tuple(nodes),
            chunks=tuple(chunks),
            assets=asset_list,
            warnings=tuple(dict.fromkeys(warnings)),
            quality={
                "node_count": len(nodes),
                "chunk_count": len(chunks),
                "anchor_coverage": anchor_count / len(nodes) if nodes else 0.0,
                "empty_text_nodes": sum(not node.normalized_text for node in nodes),
            },
        )

    def _chunks(self, canonical_id: str, nodes: list[DocumentNode]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        text_parts: list[str] = []
        chunk_nodes: list[DocumentNode] = []

        def flush() -> None:
            if not text_parts:
                return
            text = "\n\n".join(text_parts)
            order = len(chunks)
            chunks.append(
                DocumentChunk(
                    chunk_id=stable_id(
                        "chunk", canonical_id, order, [node.node_id for node in chunk_nodes], text
                    ),
                    order=order,
                    text=text,
                    node_ids=tuple(node.node_id for node in chunk_nodes),
                    anchors=tuple(node.source_anchor for node in chunk_nodes),
                    char_count=len(text),
                )
            )
            text_parts.clear()
            chunk_nodes.clear()

        for node in nodes:
            if not node.normalized_text:
                continue
            projected_length = sum(len(part) for part in text_parts) + len(node.normalized_text)
            if text_parts and projected_length > self.chunk_chars:
                flush()
            text_parts.append(node.text.strip())
            chunk_nodes.append(node)
        flush()
        return chunks

"""Canonical Document projection into versioned GBrain Markdown pages."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..document.models import CanonicalDocument


@dataclass(frozen=True)
class ProjectionLink:
    from_slug: str
    to_slug: str
    link_type: str


@dataclass(frozen=True)
class ProjectionManifest:
    root: Path
    document_slug: str
    page_paths: tuple[Path, ...]
    links: tuple[ProjectionLink, ...]


class GBrainProjectionBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def build(self, document: CanonicalDocument) -> ProjectionManifest:
        document_slug = f"documents/{document.canonical_document_id}"
        page_paths: list[Path] = []
        links: list[ProjectionLink] = []

        document_path = self.root / f"{document_slug}.md"
        document_body = "\n".join(
            [
                f"# {document.source.file_name}",
                "",
                f"Canonical document: `{document.canonical_document_id}`",
                "",
                f"Source SHA-256: `{document.source.sha256}`",
                "",
                "## Chunks",
                "",
                *[
                    f"- [[documents/{document.canonical_document_id}/chunks/{chunk.chunk_id}|Chunk {chunk.order + 1}]]"
                    for chunk in document.chunks
                ],
                "",
            ]
        )
        self._write_page(
            document_path,
            {
                "type": "note",
                "title": document.source.file_name,
                "canonical_document_id": document.canonical_document_id,
                "source_sha256": document.source.sha256,
                "parser": document.parse.parser,
                "parser_version": document.parse.parser_version,
                "tags": ["canonical-document", "document-infrastructure"],
            },
            document_body,
        )
        page_paths.append(document_path)

        for chunk in document.chunks:
            slug = f"documents/{document.canonical_document_id}/chunks/{chunk.chunk_id}"
            path = self.root / f"{slug}.md"
            anchors = [anchor.model_dump(mode="json", exclude_none=True) for anchor in chunk.anchors]
            body = "\n".join(
                [
                    f"# Chunk {chunk.order + 1}: {document.source.file_name}",
                    "",
                    chunk.text,
                    "",
                    "## Provenance",
                    "",
                    f"Derived from [[{document_slug}|{document.source.file_name}]].",
                    "",
                    f"Canonical nodes: `{', '.join(chunk.node_ids)}`",
                    "",
                ]
            )
            self._write_page(
                path,
                {
                    "type": "note",
                    "title": f"{document.source.file_name} / Chunk {chunk.order + 1}",
                    "canonical_document_id": document.canonical_document_id,
                    "canonical_chunk_id": chunk.chunk_id,
                    "canonical_node_ids": list(chunk.node_ids),
                    "source_anchors_json": json.dumps(anchors, ensure_ascii=False, separators=(",", ":")),
                    "tags": ["canonical-chunk", "document-evidence"],
                },
                body,
            )
            page_paths.append(path)
            links.append(ProjectionLink(slug, document_slug, "derived_from"))

        return ProjectionManifest(
            root=self.root,
            document_slug=document_slug,
            page_paths=tuple(page_paths),
            links=tuple(links),
        )

    @staticmethod
    def _write_page(path: Path, frontmatter: dict[str, object], body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
        content = f"---\n{serialized}\n---\n\n{body.rstrip()}\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)

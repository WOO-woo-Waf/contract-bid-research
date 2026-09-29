"""Versioned, location-aware Canonical Document models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceFile(FrozenModel):
    file_name: str
    media_type: str
    sha256: str
    size_bytes: int = Field(ge=0)


class ParseMetadata(FrozenModel):
    parser: str = "mineru"
    parser_version: str | None = None
    backend: str | None = None
    task_id: str | None = None
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    artifact_hashes: dict[str, str] = Field(default_factory=dict)


class SourceAnchor(FrozenModel):
    kind: Literal["page_bbox", "page", "logical", "unknown"] = "unknown"
    page_index: int | None = Field(default=None, ge=0)
    bbox: tuple[float, float, float, float] | None = None
    coordinate_space: str | None = None
    raw_path: str | None = None

    @field_validator("bbox")
    @classmethod
    def validate_bbox(
        cls, value: tuple[float, float, float, float] | None
    ) -> tuple[float, float, float, float] | None:
        if value is None:
            return None
        x0, y0, x1, y1 = value
        if x1 < x0 or y1 < y0:
            raise ValueError("bbox must satisfy x1 >= x0 and y1 >= y0")
        return value


class Asset(FrozenModel):
    asset_id: str
    relative_path: str
    media_type: str
    sha256: str
    size_bytes: int = Field(ge=0)


class DocumentNode(FrozenModel):
    node_id: str
    parent_id: str | None = None
    type: str
    order: int = Field(ge=0)
    text: str = ""
    normalized_text: str = ""
    html: str | None = None
    latex: str | None = None
    source_anchor: SourceAnchor = Field(default_factory=SourceAnchor)
    asset_refs: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(FrozenModel):
    chunk_id: str
    order: int = Field(ge=0)
    text: str
    node_ids: tuple[str, ...]
    anchors: tuple[SourceAnchor, ...]
    char_count: int = Field(ge=0)


class CanonicalDocument(FrozenModel):
    schema_version: str = "1.0.0"
    canonical_document_id: str
    source: SourceFile
    parse: ParseMetadata
    markdown: str = ""
    nodes: tuple[DocumentNode, ...]
    chunks: tuple[DocumentChunk, ...]
    assets: tuple[Asset, ...] = ()
    warnings: tuple[str, ...] = ()
    quality: dict[str, float | int | str] = Field(default_factory=dict)

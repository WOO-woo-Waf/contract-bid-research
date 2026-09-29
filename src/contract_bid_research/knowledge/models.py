"""Stable retrieval result models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..document.models import SourceAnchor


class EvidenceHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    canonical_document_id: str
    text: str
    score: float
    retrieval_mode: Literal["keyword", "vector", "hybrid", "rerank"]
    node_ids: tuple[str, ...]
    anchors: tuple[SourceAnchor, ...]
    rank: int = Field(ge=1)


class RerankResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=0)
    relevance_score: float

"""Stable object-oriented ports shared by future document businesses."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .document.models import CanonicalDocument
from .knowledge.models import EvidenceHit


class DocumentParser(Protocol):
    def parse_file(self, path: Path) -> CanonicalDocument:
        """Parse one file into the stable, parser-neutral document model."""


class DocumentRepository(Protocol):
    def save(self, document: CanonicalDocument) -> Path:
        """Persist an immutable document version and return its location."""

    def load(self, canonical_document_id: str) -> CanonicalDocument:
        """Load a canonical document version by stable identifier."""


class KnowledgeIndex(Protocol):
    def index_document(self, document: CanonicalDocument) -> int:
        """Index a canonical document and return the number of indexed chunks."""

    def search(self, query: str, *, limit: int = 10) -> Sequence[EvidenceHit]:
        """Return evidence-bearing retrieval hits."""


class ReviewRule(Protocol):
    """Future review algorithms plug in here without changing infrastructure."""

    @property
    def rule_id(self) -> str: ...

    def evaluate(self, document: CanonicalDocument, evidence: KnowledgeIndex) -> Sequence[object]: ...

"""Filesystem repository for immutable Canonical Document versions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import CanonicalDocument


class JsonDocumentRepository:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save(self, document: CanonicalDocument) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{document.canonical_document_id}.json"
        payload = document.model_dump_json(indent=2)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.root, delete=False) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        os.replace(temporary, target)
        return target

    def load(self, canonical_document_id: str) -> CanonicalDocument:
        target = self.root / f"{canonical_document_id}.json"
        return CanonicalDocument.model_validate(json.loads(target.read_text(encoding="utf-8")))

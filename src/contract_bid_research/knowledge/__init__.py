"""Portable retrieval and GBrain integration."""

from .gbrain import GBrainAdapter, GBrainCommandError
from .models import EvidenceHit, RerankResult
from .model_api import ModelAPIClient, ModelAPIError
from .projection import GBrainProjectionBuilder, ProjectionManifest
from .sqlite_index import SQLiteKnowledgeIndex

__all__ = [
    "EvidenceHit",
    "GBrainAdapter",
    "GBrainCommandError",
    "GBrainProjectionBuilder",
    "ModelAPIClient",
    "ModelAPIError",
    "ProjectionManifest",
    "RerankResult",
    "SQLiteKnowledgeIndex",
]

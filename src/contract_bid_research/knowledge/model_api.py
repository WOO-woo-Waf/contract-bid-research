"""OpenAI-compatible embeddings plus provider-compatible reranking."""

from __future__ import annotations

from typing import Iterable

import httpx

from ..config import ModelAPISettings
from .models import RerankResult


class ModelAPIError(RuntimeError):
    pass


class ModelAPIClient:
    def __init__(
        self,
        settings: ModelAPISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.http = httpx.Client(
            base_url=settings.base_url,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=settings.timeout_s,
            transport=transport,
            trust_env=True,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "ModelAPIClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def list_models(self) -> tuple[str, ...]:
        try:
            response = self.http.get("/models")
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelAPIError(f"model listing failed: {exc}") from exc
        return tuple(str(item["id"]) for item in payload.get("data", []) if isinstance(item, dict) and item.get("id"))

    def embed(self, texts: Iterable[str], *, batch_size: int = 64) -> list[list[float]]:
        items = [text for text in texts]
        if not items:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in items):
            raise ValueError("embedding inputs must be non-empty strings")
        vectors: list[list[float]] = []
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            try:
                response = self.http.post(
                    "/embeddings",
                    json={"model": self.settings.embedding_model, "input": batch},
                )
                response.raise_for_status()
                payload = response.json()
                ordered = sorted(payload["data"], key=lambda item: item.get("index", 0))
                batch_vectors = [item["embedding"] for item in ordered]
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                raise ModelAPIError(f"embedding request failed: {exc}") from exc
            if len(batch_vectors) != len(batch):
                raise ModelAPIError("embedding response count does not match input count")
            for vector in batch_vectors:
                if len(vector) != self.settings.embedding_dimensions:
                    raise ModelAPIError(
                        f"embedding dimension mismatch: expected {self.settings.embedding_dimensions}, got {len(vector)}"
                    )
                vectors.append([float(value) for value in vector])
        return vectors

    def rerank(self, query: str, documents: Iterable[str], *, top_n: int | None = None) -> list[RerankResult]:
        items = list(documents)
        if not query.strip() or not items:
            return []
        try:
            response = self.http.post(
                "/rerank",
                json={
                    "model": self.settings.rerank_model,
                    "query": query,
                    "documents": items,
                    "top_n": top_n or len(items),
                    "return_documents": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            results = [RerankResult.model_validate(item) for item in payload["results"]]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ModelAPIError(f"rerank request failed: {exc}") from exc
        return results

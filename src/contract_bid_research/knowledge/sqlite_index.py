"""Portable SQLite FTS + real-vector + rerank knowledge index."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Literal

import numpy as np

from ..document.models import CanonicalDocument, SourceAnchor
from .model_api import ModelAPIClient
from .models import EvidenceHit

_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
_WORD = re.compile(r"[A-Za-z0-9_]+")


def lexical_terms(text: str) -> list[str]:
    terms = [match.group(0).lower() for match in _WORD.finditer(text)]
    for match in _CJK_RUN.finditer(text):
        run = match.group(0)
        if len(run) == 1:
            terms.append(run)
        else:
            terms.extend(run[index : index + 2] for index in range(len(run) - 1))
    return list(dict.fromkeys(terms))


def _serialize_vector(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _cosine(query: np.ndarray, candidate: np.ndarray) -> float:
    denominator = float(np.linalg.norm(query) * np.linalg.norm(candidate))
    if denominator == 0:
        return 0.0
    return float(np.dot(query, candidate) / denominator)


class SQLiteKnowledgeIndex:
    """Small deployable baseline with stable evidence-bearing results."""

    def __init__(self, path: Path, model_client: ModelAPIClient) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.model_client = model_client
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteKnowledgeIndex":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents (
                canonical_document_id TEXT PRIMARY KEY,
                source_json TEXT NOT NULL,
                parse_json TEXT NOT NULL,
                schema_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                canonical_document_id TEXT NOT NULL,
                text TEXT NOT NULL,
                lexical_text TEXT NOT NULL,
                node_ids_json TEXT NOT NULL,
                anchors_json TEXT NOT NULL,
                embedding BLOB NOT NULL,
                embedding_dimensions INTEGER NOT NULL,
                FOREIGN KEY(canonical_document_id) REFERENCES documents(canonical_document_id)
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(canonical_document_id);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                lexical_text,
                tokenize='unicode61'
            );
            """
        )
        self.connection.commit()

    def index_document(self, document: CanonicalDocument) -> int:
        vectors = self.model_client.embed(chunk.text for chunk in document.chunks)
        if len(vectors) != len(document.chunks):
            raise RuntimeError("embedding count does not match document chunks")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO documents(canonical_document_id, source_json, parse_json, schema_version)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(canonical_document_id) DO UPDATE SET
                    source_json=excluded.source_json,
                    parse_json=excluded.parse_json,
                    schema_version=excluded.schema_version
                """,
                (
                    document.canonical_document_id,
                    document.source.model_dump_json(),
                    document.parse.model_dump_json(),
                    document.schema_version,
                ),
            )
            for chunk, vector in zip(document.chunks, vectors, strict=True):
                lexical_text = " ".join(lexical_terms(chunk.text))
                self.connection.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,))
                self.connection.execute(
                    """
                    INSERT INTO chunks(
                        chunk_id, canonical_document_id, text, lexical_text,
                        node_ids_json, anchors_json, embedding, embedding_dimensions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        canonical_document_id=excluded.canonical_document_id,
                        text=excluded.text,
                        lexical_text=excluded.lexical_text,
                        node_ids_json=excluded.node_ids_json,
                        anchors_json=excluded.anchors_json,
                        embedding=excluded.embedding,
                        embedding_dimensions=excluded.embedding_dimensions
                    """,
                    (
                        chunk.chunk_id,
                        document.canonical_document_id,
                        chunk.text,
                        lexical_text,
                        json.dumps(chunk.node_ids, ensure_ascii=False),
                        json.dumps([anchor.model_dump(mode="json") for anchor in chunk.anchors], ensure_ascii=False),
                        _serialize_vector(vector),
                        len(vector),
                    ),
                )
                self.connection.execute(
                    "INSERT INTO chunks_fts(chunk_id, lexical_text) VALUES (?, ?)",
                    (chunk.chunk_id, lexical_text),
                )
        return len(document.chunks)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        mode: Literal["keyword", "vector", "hybrid"] = "hybrid",
        rerank: bool = True,
    ) -> list[EvidenceHit]:
        if not query.strip() or limit < 1:
            return []
        pool_size = max(limit * 4, 20)
        keyword = self._keyword_scores(query, pool_size) if mode in {"keyword", "hybrid"} else {}
        vector = self._vector_scores(query, pool_size) if mode in {"vector", "hybrid"} else {}
        if mode == "keyword":
            merged = keyword
        elif mode == "vector":
            merged = vector
        else:
            merged = self._rrf(keyword, vector)
        ranked_ids = sorted(merged, key=merged.get, reverse=True)[:pool_size]
        rows = self._rows(ranked_ids)
        ordered_rows = [rows[chunk_id] for chunk_id in ranked_ids if chunk_id in rows]

        retrieval_mode: Literal["keyword", "vector", "hybrid", "rerank"] = mode
        if rerank and ordered_rows:
            reranked = self.model_client.rerank(query, [row["text"] for row in ordered_rows], top_n=limit)
            ordered = [(ordered_rows[item.index], item.relevance_score) for item in reranked]
            retrieval_mode = "rerank"
        else:
            ordered = [(row, merged[row["chunk_id"]]) for row in ordered_rows[:limit]]

        hits: list[EvidenceHit] = []
        for rank, (row, score) in enumerate(ordered[:limit], 1):
            anchors = tuple(
                SourceAnchor.model_validate(item) for item in json.loads(row["anchors_json"])
            )
            hits.append(
                EvidenceHit(
                    chunk_id=row["chunk_id"],
                    canonical_document_id=row["canonical_document_id"],
                    text=row["text"],
                    score=float(score),
                    retrieval_mode=retrieval_mode,
                    node_ids=tuple(json.loads(row["node_ids_json"])),
                    anchors=anchors,
                    rank=rank,
                )
            )
        return hits

    def _keyword_scores(self, query: str, limit: int) -> dict[str, float]:
        terms = lexical_terms(query)
        if not terms:
            return {}
        expression = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
        rows = self.connection.execute(
            "SELECT chunk_id, lexical_text, bm25(chunks_fts) AS rank FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (expression, limit),
        ).fetchall()
        query_terms = set(terms)
        scores: dict[str, float] = {}
        for row in rows:
            candidate_terms = set(str(row["lexical_text"]).split())
            coverage = len(query_terms & candidate_terms) / len(query_terms)
            bm25_score = 1.0 / (1.0 + abs(float(row["rank"])))
            scores[row["chunk_id"]] = coverage + 0.1 * bm25_score
        return scores

    def _vector_scores(self, query: str, limit: int) -> dict[str, float]:
        vector = np.asarray(self.model_client.embed([query])[0], dtype=np.float32)
        rows = self.connection.execute(
            "SELECT chunk_id, embedding, embedding_dimensions FROM chunks"
        ).fetchall()
        scores: list[tuple[str, float]] = []
        for row in rows:
            if int(row["embedding_dimensions"]) != vector.size:
                continue
            candidate = np.frombuffer(row["embedding"], dtype=np.float32)
            scores.append((row["chunk_id"], _cosine(vector, candidate)))
        scores.sort(key=lambda item: item[1], reverse=True)
        return dict(scores[:limit])

    @staticmethod
    def _rrf(*rankings: dict[str, float], k: int = 60) -> dict[str, float]:
        merged: dict[str, float] = {}
        for scores in rankings:
            ranked = sorted(scores, key=scores.get, reverse=True)
            for rank, chunk_id in enumerate(ranked, 1):
                merged[chunk_id] = merged.get(chunk_id, 0.0) + 1.0 / (k + rank)
        return merged

    def _rows(self, chunk_ids: list[str]) -> dict[str, sqlite3.Row]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" for _ in chunk_ids)
        rows = self.connection.execute(
            f"SELECT * FROM chunks WHERE chunk_id IN ({placeholders})", chunk_ids
        ).fetchall()
        return {row["chunk_id"]: row for row in rows}

    def statistics(self) -> dict[str, int]:
        documents = int(self.connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        chunks = int(self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        embedded = int(
            self.connection.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[0]
        )
        return {"documents": documents, "chunks": chunks, "embedded_chunks": embedded}

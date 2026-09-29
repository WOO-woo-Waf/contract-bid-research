"""Thin CLI for portable document and knowledge infrastructure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapters.mineru import MinerUClient, MinerUError
from .config import AppSettings, ConfigurationError, migrate_legacy_env
from .document.models import CanonicalDocument
from .document.repository import JsonDocumentRepository
from .knowledge.gbrain import GBrainAdapter
from .knowledge.model_api import ModelAPIClient
from .knowledge.projection import GBrainProjectionBuilder
from .knowledge.sqlite_index import SQLiteKnowledgeIndex


def _json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _load_document(path: Path) -> CanonicalDocument:
    return CanonicalDocument.model_validate_json(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contract-bid-infra")
    parser.add_argument("--env-file", default=".env", help="dotenv path (default: .env)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("config-migrate", help="normalize the observed legacy URL/token .env")
    subparsers.add_parser("config-check", help="validate config and print a redacted snapshot")
    subparsers.add_parser("model-smoke", help="call real models, embeddings, and reranker")

    parse = subparsers.add_parser("parse", help="stream a file to MinerU and save Canonical JSON")
    parse.add_argument("file", type=Path)
    parse.add_argument("--repository", type=Path)

    project = subparsers.add_parser("project", help="project Canonical JSON to GBrain Markdown")
    project.add_argument("document", type=Path)
    project.add_argument("--output", type=Path, required=True)

    index = subparsers.add_parser("kb-index", help="index Canonical JSON in portable SQLite")
    index.add_argument("document", type=Path)

    search = subparsers.add_parser("kb-search", help="search portable SQLite knowledge index")
    search.add_argument("query")
    search.add_argument("--mode", choices=["keyword", "vector", "hybrid"], default="hybrid")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--no-rerank", action="store_true")

    subparsers.add_parser("gbrain-init", help="initialize isolated PGLite GBrain")
    gimport = subparsers.add_parser("gbrain-import", help="project and import one Canonical document")
    gimport.add_argument("document", type=Path)
    gimport.add_argument("--projection-root", type=Path)
    gsearch = subparsers.add_parser("gbrain-search", help="run GBrain keyword and hybrid search")
    gsearch.add_argument("query")
    gsearch.add_argument("--limit", type=int, default=5)
    evidence = subparsers.add_parser("gbrain-evidence", help="map GBrain hybrid hits to Canonical anchors")
    evidence.add_argument("document", type=Path)
    evidence.add_argument("query")
    evidence.add_argument("--limit", type=int, default=5)
    graph = subparsers.add_parser("gbrain-graph", help="traverse GBrain typed links")
    graph.add_argument("slug")
    graph.add_argument("--depth", type=int, default=2)
    subparsers.add_parser("gbrain-stats", help="show GBrain page/chunk/embed/link counts")
    subparsers.add_parser("gbrain-doctor", help="run structured GBrain health checks")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env_path = Path(args.env_file)
    try:
        if args.command == "config-migrate":
            changed = migrate_legacy_env(env_path)
            _json({"status": "migrated" if changed else "already_normalized", "path": str(env_path)})
            return 0

        settings = AppSettings.load(env_path)
        if args.command == "config-check":
            _json(settings.redacted_snapshot())
            return 0

        if args.command == "model-smoke":
            with ModelAPIClient(settings.model_api) as client:
                models = client.list_models()
                vectors = client.embed(["文档来源锚点", "知识库混合检索"])
                reranked = client.rerank(
                    "如何回到原始文档位置？",
                    ["使用页码和边界框来源锚点。", "生成封面。", "数据库定时备份。"],
                    top_n=3,
                )
            _json(
                {
                    "model_count": len(models),
                    "embedding_model": settings.model_api.embedding_model,
                    "embedding_vectors": len(vectors),
                    "embedding_dimensions": len(vectors[0]),
                    "rerank_model": settings.model_api.rerank_model,
                    "rerank_order": [item.index for item in reranked],
                }
            )
            return 0

        if args.command == "parse":
            repository_root = args.repository or settings.storage.data_root / "canonical"
            with MinerUClient(settings.mineru, artifact_root=settings.storage.artifacts_root) as client:
                document = client.parse_file(args.file)
            target = JsonDocumentRepository(repository_root).save(document)
            _json(
                {
                    "canonical_document_id": document.canonical_document_id,
                    "nodes": len(document.nodes),
                    "chunks": len(document.chunks),
                    "anchor_coverage": document.quality.get("anchor_coverage"),
                    "path": str(target),
                }
            )
            return 0

        if args.command == "project":
            document = _load_document(args.document)
            manifest = GBrainProjectionBuilder(args.output).build(document)
            _json(
                {
                    "document_slug": manifest.document_slug,
                    "pages": len(manifest.page_paths),
                    "typed_links": len(manifest.links),
                    "root": str(manifest.root),
                }
            )
            return 0

        if args.command == "kb-index":
            document = _load_document(args.document)
            with ModelAPIClient(settings.model_api) as model_client:
                with SQLiteKnowledgeIndex(settings.storage.knowledge_db, model_client) as index:
                    count = index.index_document(document)
                    stats = index.statistics()
            _json({"indexed_chunks": count, "statistics": stats})
            return 0

        if args.command == "kb-search":
            with ModelAPIClient(settings.model_api) as model_client:
                with SQLiteKnowledgeIndex(settings.storage.knowledge_db, model_client) as index:
                    hits = index.search(
                        args.query,
                        limit=args.limit,
                        mode=args.mode,
                        rerank=not args.no_rerank,
                    )
            _json([hit.model_dump(mode="json") for hit in hits])
            return 0

        gbrain = GBrainAdapter(
            settings.storage.gbrain_repository,
            settings.storage.gbrain_home,
            settings.model_api,
        )
        if args.command == "gbrain-init":
            output = gbrain.initialize()
            _json({"status": "ok", "output_tail": output[-1000:]})
            return 0
        if args.command == "gbrain-import":
            document = _load_document(args.document)
            projection_root = args.projection_root or settings.storage.artifacts_root / "gbrain_projection"
            manifest = GBrainProjectionBuilder(projection_root).build(document)
            gbrain.initialize()
            import_output = gbrain.import_directory(manifest.root)
            link_count = gbrain.add_links(manifest.links)
            _json(
                {
                    "pages": len(manifest.page_paths),
                    "typed_links": link_count,
                    "import_output_tail": import_output[-1000:],
                    "statistics": gbrain.statistics(),
                }
            )
            return 0
        if args.command == "gbrain-search":
            _json(
                {
                    "keyword": gbrain.keyword_search(args.query, limit=args.limit),
                    "hybrid": gbrain.hybrid_search(args.query, limit=args.limit),
                }
            )
            return 0
        if args.command == "gbrain-evidence":
            document = _load_document(args.document)
            hits = gbrain.evidence_search(
                args.query,
                {document.canonical_document_id: document},
                limit=args.limit,
            )
            _json([hit.model_dump(mode="json") for hit in hits])
            return 0
        if args.command == "gbrain-graph":
            _json(gbrain.graph(args.slug, depth=args.depth))
            return 0
        if args.command == "gbrain-stats":
            _json(gbrain.statistics())
            return 0
        if args.command == "gbrain-doctor":
            _json(gbrain.doctor())
            return 0
    except (ConfigurationError, MinerUError, OSError, RuntimeError, ValueError) as exc:
        category = getattr(exc, "category", exc.__class__.__name__)
        print(json.dumps({"status": "error", "category": category, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Public-CLI adapter around a pinned external GBrain checkout."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..config import ModelAPISettings
from ..document.models import CanonicalDocument
from .models import EvidenceHit
from .projection import ProjectionLink


class GBrainCommandError(RuntimeError):
    def __init__(self, command: tuple[str, ...], returncode: int, message: str) -> None:
        super().__init__(f"GBrain command failed ({returncode}): {' '.join(command)}\n{message[-2000:]}")
        self.command = command
        self.returncode = returncode


class GBrainAdapter:
    def __init__(
        self,
        repository: Path,
        home: Path,
        model_settings: ModelAPISettings,
        *,
        timeout_s: float = 300,
    ) -> None:
        self.repository = repository.resolve()
        self.home = home.resolve()
        self.model_settings = model_settings
        self.timeout_s = timeout_s
        if not (self.repository / "src" / "cli.ts").is_file():
            raise ValueError(f"not a GBrain checkout: {self.repository}")

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "GBRAIN_HOME": str(self.home),
                "GBRAIN_SKIP_STARTUP_HOOKS": "1",
                "OPENAI_BASE_URL": self.model_settings.base_url,
                "OPENAI_API_KEY": self.model_settings.api_key,
                "GBRAIN_EMBEDDING_MODEL": f"openai:{self.model_settings.embedding_model}",
                "GBRAIN_EMBEDDING_DIMENSIONS": str(self.model_settings.embedding_dimensions),
            }
        )
        return env

    def run(self, *args: str, timeout_s: float | None = None) -> str:
        command = ("bun", "run", "src/cli.ts", *args)
        try:
            result = subprocess.run(
                command,
                cwd=self.repository,
                env=self._environment(),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_s or self.timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GBrainCommandError(command, -1, str(exc)) from exc
        if result.returncode != 0:
            raise GBrainCommandError(command, result.returncode, result.stderr or result.stdout)
        return result.stdout.strip()

    def call(self, operation: str, parameters: dict[str, Any]) -> Any:
        output = self.run("call", operation, json.dumps(parameters, ensure_ascii=False))
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise GBrainCommandError(("call", operation), 0, f"non-JSON output: {output[-2000:]}") from exc

    def initialize(self, *, force: bool = False) -> str:
        config_path = self.home / ".gbrain" / "config.json"
        if config_path.is_file() and not force:
            self.configure_retrieval()
            return "already_initialized"
        self.home.mkdir(parents=True, exist_ok=True)
        args = [
            "init",
            "--pglite",
            "--embedding-model",
            f"openai:{self.model_settings.embedding_model}",
            "--embedding-dimensions",
            str(self.model_settings.embedding_dimensions),
        ]
        if force:
            args.append("--force")
        output = self.run(*args, timeout_s=600)
        self.configure_retrieval()
        return output

    def configure_retrieval(self) -> None:
        """Use GBrain for hybrid recall; external qwen3 handles reranking."""

        self.run("config", "set", "search.mode", "conservative")
        self.run("config", "set", "search.reranker.enabled", "false")

    def import_directory(self, path: Path) -> str:
        source = path.resolve()
        if not source.is_dir():
            raise ValueError(f"projection directory does not exist: {source}")
        # GBrain intentionally honors an enclosing repository's .gitignore.
        # Canonical projections are runtime artifacts and therefore ignored in
        # this repository, so stage them outside the worktree for import while
        # preserving their relative paths/slugs.
        with tempfile.TemporaryDirectory(prefix="contract-bid-gbrain-import-") as temporary_root:
            staged = Path(temporary_root) / "projection"
            shutil.copytree(source, staged)
            return self.run("import", str(staged), "--fresh", timeout_s=1800)

    def add_links(self, links: Iterable[ProjectionLink]) -> int:
        count = 0
        for link in links:
            self.call(
                "add_link",
                {
                    "from": link.from_slug,
                    "to": link.to_slug,
                    "link_type": link.link_type,
                    "link_source": "canonical-projection",
                },
            )
            count += 1
        return count

    def keyword_search(self, query: str, *, limit: int = 10) -> Any:
        return self.call("search", {"query": query, "limit": limit, "mode": "conservative"})

    def hybrid_search(self, query: str, *, limit: int = 10) -> Any:
        return self.call(
            "query",
            {"query": query, "limit": limit, "expand": False, "mode": "conservative"},
        )

    def graph(self, slug: str, *, depth: int = 2) -> Any:
        result = self.call("traverse_graph", {"slug": slug, "depth": depth, "direction": "both"})
        if not isinstance(result, list):
            return result
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in result:
            if not isinstance(item, dict):
                continue
            key = (str(item.get("from_slug")), str(item.get("to_slug")), str(item.get("link_type")))
            current = unique.get(key)
            if current is None or int(item.get("depth", 999)) < int(current.get("depth", 999)):
                unique[key] = item
        return list(unique.values())

    def evidence_search(
        self,
        query: str,
        documents: Mapping[str, CanonicalDocument],
        *,
        limit: int = 10,
    ) -> list[EvidenceHit]:
        """Map GBrain candidate pages back to Canonical chunks and anchors."""

        raw = self.hybrid_search(query, limit=max(limit * 4, 20))
        if not isinstance(raw, list):
            return []
        hits: list[EvidenceHit] = []
        seen: set[tuple[str, str]] = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug", ""))
            parts = slug.split("/")
            if len(parts) < 4 or parts[0] != "documents" or parts[2] != "chunks":
                continue
            document_id, chunk_id = parts[1], parts[3]
            # Older/newer GBrain slugs may have additional segments; fall back
            # to the last path component for the projected chunk id.
            chunk_id = parts[-1]
            key = (document_id, chunk_id)
            if key in seen or document_id not in documents:
                continue
            chunk = next(
                (candidate for candidate in documents[document_id].chunks if candidate.chunk_id == chunk_id),
                None,
            )
            if chunk is None:
                continue
            seen.add(key)
            hits.append(
                EvidenceHit(
                    chunk_id=chunk.chunk_id,
                    canonical_document_id=document_id,
                    text=chunk.text,
                    score=float(item.get("score", 0.0)),
                    retrieval_mode="hybrid",
                    node_ids=chunk.node_ids,
                    anchors=chunk.anchors,
                    rank=len(hits) + 1,
                )
            )
            if len(hits) >= limit:
                break
        return hits

    def statistics(self) -> Any:
        return self.call("get_stats", {})

    def doctor(self) -> Any:
        return self.call("run_doctor", {})

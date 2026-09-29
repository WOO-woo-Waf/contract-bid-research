"""Strict-TLS, streaming-file adapter for the deployed MinerU task API."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import httpx

from ..config import MinerUSettings
from ..document.builder import CanonicalDocumentBuilder
from ..document.ids import sha256_bytes, stable_id
from ..document.models import Asset, CanonicalDocument, ParseMetadata


class MinerUError(RuntimeError):
    """Base error carrying a stable machine-readable category."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


def _http_error(category: str, operation: str, exc: httpx.HTTPError) -> MinerUError:
    message = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
        return MinerUError(
            "tls_verification_failed",
            f"MinerU {operation} rejected the server certificate: {message}",
        )
    return MinerUError(category, f"MinerU {operation} failed: {message}")


@dataclass(frozen=True)
class ParseOptions:
    language: str = "ch"
    backend: str = "vlm-engine"
    effort: str = "high"
    parse_method: str = "auto"
    formula_enable: bool = True
    table_enable: bool = True
    image_analysis: bool = True

    def form_data(self) -> dict[str, str]:
        def boolean(value: bool) -> str:
            return "true" if value else "false"

        return {
            "lang_list": self.language,
            "backend": self.backend,
            "effort": self.effort,
            "parse_method": self.parse_method,
            "formula_enable": boolean(self.formula_enable),
            "table_enable": boolean(self.table_enable),
            "image_analysis": boolean(self.image_analysis),
            "return_md": "true",
            "return_middle_json": "true",
            "return_model_output": "false",
            "return_content_list": "true",
            "return_images": "true",
            "response_format_zip": "true",
            "return_original_file": "false",
        }


@dataclass(frozen=True)
class MinerUResultBundle:
    markdown: str
    content_list: list[Any]
    middle_json: dict[str, Any] | list[Any] | None
    assets: tuple[Asset, ...]
    artifact_hashes: dict[str, str]
    members: tuple[str, ...]

    @classmethod
    def from_zip(cls, payload: bytes) -> "MinerUResultBundle":
        try:
            archive = zipfile.ZipFile(BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise MinerUError("invalid_zip", "MinerU result is not a valid ZIP archive") from exc

        members: list[str] = []
        blobs: dict[str, bytes] = {}
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise MinerUError("invalid_zip", f"unsafe ZIP member: {info.filename!r}")
            if info.is_dir():
                continue
            members.append(info.filename)
            blobs[info.filename] = archive.read(info)

        md_names = sorted(name for name in members if name.lower().endswith(".md"))
        content_names = sorted(
            name
            for name in members
            if name.lower().endswith("_content_list.json")
            and not name.lower().endswith("_content_list_v2.json")
        )
        if not content_names:
            content_names = sorted(
                name for name in members if PurePosixPath(name).name.lower() == "content_list.json"
            )
        middle_names = sorted(name for name in members if name.lower().endswith("_middle.json"))
        if not middle_names:
            middle_names = sorted(name for name in members if PurePosixPath(name).name.lower() == "middle.json")

        if not md_names:
            raise MinerUError("missing_required_artifact", "MinerU ZIP does not contain Markdown")
        if not content_names:
            raise MinerUError("missing_required_artifact", "MinerU ZIP does not contain content_list JSON")

        try:
            markdown = blobs[md_names[0]].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MinerUError("invalid_markdown", "Markdown is not UTF-8") from exc
        try:
            content_list = json.loads(blobs[content_names[0]])
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MinerUError("invalid_content_list_json", "content_list is not valid UTF-8 JSON") from exc
        if not isinstance(content_list, list):
            if isinstance(content_list, dict) and isinstance(content_list.get("content_list"), list):
                content_list = content_list["content_list"]
            else:
                raise MinerUError("invalid_content_list_json", "content_list root must be a list")

        middle_json: dict[str, Any] | list[Any] | None = None
        if middle_names:
            try:
                middle_json = json.loads(blobs[middle_names[0]])
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise MinerUError("invalid_middle_json", "middle JSON is invalid") from exc

        assets: list[Asset] = []
        for name in members:
            media_type = mimetypes.guess_type(name)[0]
            if not media_type or not media_type.startswith("image/"):
                continue
            blob = blobs[name]
            assets.append(
                Asset(
                    asset_id=stable_id("asset", name, sha256_bytes(blob)),
                    relative_path=name,
                    media_type=media_type,
                    sha256=sha256_bytes(blob),
                    size_bytes=len(blob),
                )
            )

        artifact_hashes = {
            "result_zip": sha256_bytes(payload),
            "markdown": sha256_bytes(blobs[md_names[0]]),
            "content_list": sha256_bytes(blobs[content_names[0]]),
        }
        if middle_names:
            artifact_hashes["middle_json"] = sha256_bytes(blobs[middle_names[0]])
        return cls(
            markdown=markdown,
            content_list=content_list,
            middle_json=middle_json,
            assets=tuple(assets),
            artifact_hashes=artifact_hashes,
            members=tuple(members),
        )


class MinerUClient:
    """Object-oriented adapter for POST /tasks and its polling lifecycle."""

    def __init__(
        self,
        settings: MinerUSettings,
        *,
        artifact_root: Path,
        builder: CanonicalDocumentBuilder | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.artifact_root = artifact_root.resolve()
        self.builder = builder or CanonicalDocumentBuilder()
        self.clock = clock
        self.sleeper = sleeper
        headers = {"Accept": "application/json"}
        if settings.token:
            headers["Authorization"] = f"Bearer {settings.token}"
        timeout = httpx.Timeout(
            connect=settings.connect_timeout_s,
            read=settings.read_timeout_s,
            write=settings.read_timeout_s,
            pool=settings.connect_timeout_s,
        )
        self.http = httpx.Client(
            base_url=settings.base_url,
            headers=headers,
            timeout=timeout,
            verify=settings.verify,
            follow_redirects=False,
            transport=transport,
            trust_env=True,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "MinerUClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def submit(self, path: Path, options: ParseOptions | None = None) -> dict[str, Any]:
        source = path.resolve()
        if not source.is_file():
            raise MinerUError("source_unavailable", f"file does not exist: {source}")
        media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        selected = options or ParseOptions()
        try:
            with source.open("rb") as handle:
                response = self.http.post(
                    "/tasks",
                    data=selected.form_data(),
                    files={"files": (source.name, handle, media_type)},
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise _http_error("submit_failed", "submit", exc) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise MinerUError("submit_failed", "MinerU submit response is not JSON") from exc
        if not isinstance(payload, dict) or not payload.get("task_id"):
            raise MinerUError("submit_failed", "MinerU submit response has no task_id")
        return payload

    def status(self, task_id: str) -> dict[str, Any]:
        try:
            response = self.http.get(f"/tasks/{task_id}")
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise _http_error("status_failed", "status", exc) from exc
        if not isinstance(payload, dict):
            raise MinerUError("status_failed", "MinerU status response is not an object")
        return payload

    def wait(self, task_id: str) -> dict[str, Any]:
        deadline = self.clock() + self.settings.task_timeout_s
        while self.clock() < deadline:
            payload = self.status(task_id)
            state = str(payload.get("status", "")).lower()
            if state in {"completed", "succeeded"}:
                return payload
            if state in {"failed", "cancelled", "canceled"}:
                raise MinerUError("parse_failed", str(payload.get("error") or f"task {state}"))
            self.sleeper(self.settings.poll_interval_s)
        raise MinerUError("task_timeout", f"MinerU task timed out: {task_id}")

    def download_result(self, task_id: str) -> bytes:
        try:
            response = self.http.get(f"/tasks/{task_id}/result")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise _http_error("result_download_failed", "result download", exc) from exc
        return response.content

    def persist_result(self, task_id: str, payload: bytes) -> Path:
        target_dir = self.artifact_root / "mineru" / task_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "result.zip"
        with tempfile.NamedTemporaryFile("wb", dir=target_dir, delete=False) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        os.replace(temporary, target)
        return target

    def parse_file(self, path: Path, options: ParseOptions | None = None) -> CanonicalDocument:
        selected = options or ParseOptions()
        submitted = self.submit(path, selected)
        task_id = str(submitted["task_id"])
        status = self.wait(task_id)
        payload = self.download_result(task_id)
        self.persist_result(task_id, payload)
        bundle = MinerUResultBundle.from_zip(payload)
        parse = ParseMetadata(
            parser="mineru",
            parser_version=str(status.get("version")) if status.get("version") else None,
            backend=str(status.get("backend") or selected.backend),
            task_id=task_id,
            artifact_hashes=bundle.artifact_hashes,
        )
        return self.builder.build(
            source_path=path,
            markdown=bundle.markdown,
            content_list=bundle.content_list,
            parse=parse,
            assets=bundle.assets,
        )

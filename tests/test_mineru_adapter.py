import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from contract_bid_research.adapters.mineru import MinerUClient, MinerUError, MinerUResultBundle
from contract_bid_research.config import MinerUSettings


def result_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sample/vlm/sample.md", "# 文档\n\n来源锚点。")
        archive.writestr(
            "sample/vlm/sample_content_list.json",
            json.dumps([{"type": "text", "text": "来源锚点。", "page_idx": 0, "bbox": [1, 2, 3, 4]}]),
        )
        archive.writestr("sample/vlm/sample_middle.json", json.dumps({"pages": []}))
        archive.writestr("sample/vlm/images/chart.png", b"png")
    return buffer.getvalue()


def test_result_bundle_validates_and_decodes_zip() -> None:
    bundle = MinerUResultBundle.from_zip(result_zip())

    assert bundle.markdown.startswith("# 文档")
    assert bundle.content_list[0]["page_idx"] == 0
    assert bundle.middle_json == {"pages": []}
    assert len(bundle.assets) == 1
    assert "result_zip" in bundle.artifact_hashes


def test_result_bundle_rejects_path_traversal() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.md", "bad")

    with pytest.raises(MinerUError, match="unsafe ZIP member"):
        MinerUResultBundle.from_zip(buffer.getvalue())


def test_client_streams_polls_and_builds_canonical(tmp_path: Path) -> None:
    states = iter(["running", "completed"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/tasks":
            assert b'name="files"' in request.read()
            return httpx.Response(202, json={"task_id": "task-123", "status": "pending"})
        if request.method == "GET" and request.url.path == "/tasks/task-123":
            return httpx.Response(200, json={"task_id": "task-123", "status": next(states), "backend": "vlm-engine"})
        if request.method == "GET" and request.url.path == "/tasks/task-123/result":
            return httpx.Response(200, content=result_zip(), headers={"content-type": "application/zip"})
        return httpx.Response(404)

    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    settings = MinerUSettings(
        base_url="https://mineru.example",
        token=None,
        ca_bundle=None,
        connect_timeout_s=1,
        read_timeout_s=1,
        task_timeout_s=10,
        poll_interval_s=0.01,
    )
    with MinerUClient(
        settings,
        artifact_root=tmp_path / "artifacts",
        transport=httpx.MockTransport(handler),
        sleeper=lambda _: None,
    ) as client:
        document = client.parse_file(source)

    assert document.parse.task_id == "task-123"
    assert document.nodes[0].source_anchor.kind == "page_bbox"
    assert (tmp_path / "artifacts" / "mineru" / "task-123" / "result.zip").is_file()


def test_client_classifies_tls_verification_failure(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed", request=request)

    source = tmp_path / "sample.pdf"
    source.write_bytes(b"pdf")
    settings = MinerUSettings(
        base_url="https://mineru.example",
        token=None,
        ca_bundle=None,
        connect_timeout_s=1,
        read_timeout_s=1,
        task_timeout_s=1,
        poll_interval_s=0.01,
    )
    with MinerUClient(
        settings,
        artifact_root=tmp_path / "artifacts",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(MinerUError) as captured:
            client.submit(source)

    assert captured.value.category == "tls_verification_failed"

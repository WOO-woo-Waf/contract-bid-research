"""Create a deterministic, non-domain Canonical Document for live smoke tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from contract_bid_research.document.builder import CanonicalDocumentBuilder
from contract_bid_research.document.models import ParseMetadata
from contract_bid_research.document.repository import JsonDocumentRepository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/live_smoke"))
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "infrastructure-fixture.txt"
    source.write_text(
        "基础文档数据必须保留页码和边界框。\n"
        "知识库支持关键词、向量、混合检索和重排。\n"
        "GBrain 是可重建的派生知识投影。\n",
        encoding="utf-8",
    )
    content_list = [
        {
            "type": "title",
            "text": "基础文档数据",
            "page_idx": 0,
            "bbox": [50, 40, 950, 120],
        },
        {
            "type": "text",
            "text": "Canonical Document 保存稳定节点、页码、边界框和解析来源，用于回到原始证据。来源锚点必须区分页坐标、逻辑位置和未知降级，不能在解析结果没有坐标时伪造边界框。每个节点和分块都保留固定标识，算法命中后可以展开对应节点并展示原文位置。",
            "page_idx": 0,
            "bbox": [50, 140, 950, 300],
        },
        {
            "type": "title",
            "text": "知识检索",
            "page_idx": 1,
            "bbox": [50, 40, 950, 120],
        },
        {
            "type": "text",
            "text": "知识索引组合中文关键词、真实向量 embedding、RRF 混合检索和 qwen3-rerank 重排。关键词路径负责精确术语和编号，向量路径负责语义召回，混合路径合并两组候选，最后由重排模型改善前几名顺序。所有返回结果必须携带 Canonical 节点和来源锚点。",
            "page_idx": 1,
            "bbox": [50, 140, 950, 300],
        },
        {
            "type": "text",
            "text": "GBrain 使用 PGLite 摄取 Markdown，建立 typed links 和关系图，索引可以从 Canonical 数据重建。它是派生知识层而不是原始文件主存储；投影页的 frontmatter 记录 document、chunk 和 node 标识，关系边表达 chunk derived_from document。",
            "page_idx": 2,
            "bbox": [50, 140, 950, 300],
        },
        {
            "type": "title",
            "text": "无关对照",
            "page_idx": 3,
            "bbox": [50, 40, 950, 120],
        },
        {
            "type": "text",
            "text": "容器镜像应保持无状态，运行时通过挂载目录保存数据库，通过环境变量注入密钥。镜像构建不包含客户文件、API token、解析结果包或本地数据库。",
            "page_idx": 3,
            "bbox": [50, 140, 950, 300],
        },
    ]
    document = CanonicalDocumentBuilder(chunk_chars=200).build(
        source_path=source,
        markdown="# 基础文档数据\n\n## 知识检索\n\n## GBrain 投影",
        content_list=content_list,
        parse=ParseMetadata(parser="smoke-fixture", parser_version="1.0.0", backend="deterministic"),
    )
    target = JsonDocumentRepository(root / "canonical").save(document)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

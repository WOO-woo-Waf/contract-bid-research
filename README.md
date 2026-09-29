# 合同审核与智能投标调研

本仓库沉淀合同审核与标书撰写方向的通用文档基础设施、开源代码评估、算法试验和二次开发准备。

当前阶段只做技术调研和可复现实证，不直接承诺生产级法律结论或自动投标能力。

当前范围收敛到 MinerU 结果适配、业务无关的 Canonical Document、GBrain 知识投影/检索评测以及开源算法适配器。领域任务、产品功能、统一模型网关、Prompt 平台和生产治理暂缓。

## 导航

- [基础设施实施与真实验证状态（2026-08-11）](docs/design-architecture/contract-bid-research/CONTRACT_BID_INFRASTRUCTURE_IMPLEMENTATION_AND_VALIDATION_STATUS_2026-08-11.md)
- [当前主文档：技术积累与基础设施设计](docs/design-architecture/contract-bid-research/CONTRACT_BID_TECHNICAL_ACCUMULATION_INFRASTRUCTURE_DESIGN_2026-08-04.md)
- [领域任务、产品功能与总体设计（远期参考）](docs/design-architecture/contract-bid-research/CONTRACT_BID_DOMAIN_TASK_FUNCTION_INFRASTRUCTURE_DESIGN_2026-08-04.md)
- [调研总览](docs/design-architecture/contract-bid-research/CONTRACT_BID_RESEARCH_ANALYSIS_2026-08-04.md)
- [任务与算法基线](docs/design-architecture/contract-bid-research/CONTRACT_BID_TASK_ALGORITHM_ANALYSIS_2026-08-04.md)
- [开源项目对比与二开建议](docs/design-architecture/contract-bid-research/OPEN_SOURCE_REUSE_ANALYSIS_2026-08-04.md)
- [验证与落地路线](docs/design-architecture/contract-bid-research/CONTRACT_BID_ROADMAP_PLAN_2026-08-04.md)
- [上游源码清单](references/UPSTREAMS.md)
- [机器可读任务分类](research/task_taxonomy.yaml)

## 目录约定

```text
docs/design-architecture/contract-bid-research/  正式调研、设计与路线文档
references/                                      上游清单及本地源码克隆（源码目录不入 Git）
scripts/                                         可复现的拉取、盘点与验证脚本
artifacts/                                       临时探测结果（不入 Git）
```

## Python 环境

```bash
conda env create -f environment.yml
conda activate contract-bid-research
python -m pip install -e .
pytest
```

本机已创建同名 Conda 环境。真实 API Key 只放在被忽略的 `.env`，不要写进文档、测试或研究数据。

## 已实现的基础设施

```text
MinerU 公网 /tasks 文件流
  -> 结果 ZIP 校验与安全解包
  -> Canonical Document（稳定 ID、Node、Chunk、Asset、SourceAnchor）
  -> SQLite FTS5 / embedding / RRF / qwen3-rerank
  -> GBrain Markdown 投影 / PGLite / typed links / graph / 证据回链
```

CLI 入口为 `contract-bid-infra`。先复制 `.env.example` 为 `.env` 并只在 `.env` 中填写真实密钥：

```bash
contract-bid-infra config-check
contract-bid-infra model-smoke
contract-bid-infra parse /path/to/document.pdf
contract-bid-infra kb-index data/canonical/<document-id>.json
contract-bid-infra kb-search "来源锚点" --mode hybrid
contract-bid-infra gbrain-import data/canonical/<document-id>.json
contract-bid-infra gbrain-evidence data/canonical/<document-id>.json "如何定位原文"
```

容器镜像和 Compose 配置见 `Dockerfile`、`compose.yaml`。镜像不包含 `.env`、API Key、客户文件或本地数据库；运行时目录使用 volume，输入目录只读挂载。构建环境若代理只监听 WSL loopback，使用实施状态文档中的 `--network=host` 构建命令。

## 已有基础设施边界

文档解析当前通过 `https://mineru.example.invalid` 的公网 `/tasks` 文件流接口调用 MinerU。本仓不重复建设 OCR、Office/PDF 解析或解析队列；`../mineru-api-docker-upgrade` 只作为既有实现和接口设计参考，未被本仓修改。当前公网入口证书不匹配，严格 TLS 调用会在上传前终止，详见实施状态文档。

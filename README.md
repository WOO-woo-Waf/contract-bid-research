# 合同审核与智能投标调研

本仓库沉淀合同审核与标书撰写方向的通用文档基础设施、开源代码评估、算法试验和二次开发准备。

当前阶段只做技术调研和可复现实证，不直接承诺生产级法律结论或自动投标能力。

当前范围收敛到 MinerU 结果适配、业务无关的 Canonical Document、GBrain 知识投影/检索评测以及开源算法适配器。领域任务、产品功能、统一模型网关、Prompt 平台和生产治理暂缓。

## 导航

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

## 已有基础设施边界

文档解析统一复用 `/root/dev/mineru-api-docker-upgrade` 中已经部署的 MinerU 3.4.4 服务及其 Canonical Document JSON 设计。本仓不重复建设 OCR、Office/PDF 解析或解析队列；当前主要补齐 MinerU 返回包适配、Canonical Document 构建与 GBrain 投影评测。Docling 只作为长尾格式和回归对照候选。

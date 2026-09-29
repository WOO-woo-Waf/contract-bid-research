# 合同审核与标书撰写方向：技术积累与基础设施设计

形成日期：2026-08-04

实施状态更新（2026-08-11）：本文的 MinerU 适配、Canonical Document、SQLite 混合检索、GBrain 投影/回链和 Docker 化已形成可运行代码并完成真实模型验证。当前代码现实和使用说明见 [基础设施实施与真实验证状态](CONTRACT_BID_INFRASTRUCTURE_IMPLEMENTATION_AND_VALIDATION_STATUS_2026-08-11.md)。

## 1. 当前阶段结论

当前阶段只积累后续合同审核和标书撰写可能共同使用的技术能力，不继续展开领域知识、领域任务标签和最终产品设计。

本阶段集中建设五项技术资产：

1. **MinerU 结果适配器**：调用已部署 MinerU 服务，可靠取得 ZIP/JSON 结果。
2. **基础文档数据层**：把 MinerU 的 Markdown、`content_list.json`、`middle.json` 和图片规范化成业务无关、版本化、可追溯的 Canonical Document。
3. **GBrain 知识投影与检索试验层**：把 Canonical Document 投影成 GBrain 可摄取的页面，用现有混合检索、图关系和评测能力做技术积累。
4. **开源组件适配与验证层**：以独立 adapter/PoC 复用 OpenContracts、易标、VerveDocs、Presidio 等项目中的成熟技术，不先组装最终产品。
5. **算法实验与评测底座**：积累固定样例、公共数据结构、指标、基线和错误分类，使后续领域算法可以直接进入可测环境。

明确延期：领域任务和业务知识、最终产品功能、统一模型网关和 Prompt 平台、企业审计/安全/可观测性、多租户生产体系以及大规模微调。

## 2. 目标与非目标

### 2.1 目标

- 让后续算法只面对稳定文档对象，不直接解析 MinerU 临时结果。
- 让基础文档数据能回到原始文件的页、坐标、段落、表格或 Office 逻辑位置。
- 验证 GBrain 能否承担派生知识页、混合检索、关系图和检索评测。
- 建立开源代码的固定版本、适配边界、验证样例和可替换接口。
- 先形成小而完整的技术闭环，再决定是否扩展为业务系统。

### 2.2 非目标

- Canonical Document 不包含合同风险、招标要求等领域结论。
- GBrain 不作为原始文件、版面数据或业务状态的唯一主存储。
- 本阶段不建设通用 LLM 平台；需要 embedding 时只在隔离 PoC 内使用 GBrain 自身配置。
- 本阶段不部署 OpenContracts、易标和 VerveDocs 的完整产品组合。
- 本阶段不以多租户生产上线为验收目标。

## 3. 已有基础与代码事实

### 3.1 MinerU

用户确认 `../mineru-api-docker-upgrade` 已部署 MinerU 3.4.4。现有项目已经覆盖：

- `POST /v1/process` 和 `GET /v1/jobs/{job_id}` 兼容接口；
- `POST /tasks`、`GET /tasks/{id}`、`GET /tasks/{id}/result` 官方异步接口；
- `POST /file_parse` 小文件同步接口；
- ZIP/JSON 返回 Markdown、`middle_json`、`content_list` 和图片；
- PDF/图片 `page_idx + bbox` 来源定位；
- Canonical Document JSON 和 SourceAnchor 设计草案。

证据文档：

- `../mineru-api-docker-upgrade/docs/design-architecture/mineru-api-streaming-upgrade/MINERU_SERVICE_API_GUIDE_2026-07-28.md`
- `../mineru-api-docker-upgrade/docs/design-architecture/mineru-api-streaming-upgrade/DOCUMENT_CONTENT_AND_SOURCE_LOCATION_DESIGN_2026-07-27.md`
- `../mineru-api-docker-upgrade/docs/design-architecture/document-parsing-infrastructure/MINERU_DOCUMENT_PARSING_INFRASTRUCTURE_ANALYSIS_2026-07-28.md`

当前缺口不是解析能力，而是**把解析结果实现成稳定、可复用的基础文档数据代码**。

### 3.2 GBrain

本地研究仓库：`../gbrain-llm-wiki-research`。

- 项目：`garrytan/gbrain`
- 固定提交：`3fafb69b077e602e1286af9cb092ed94455657a8`
- 版本：`0.42.66.0`
- 许可证：MIT
- 技术栈：TypeScript/Bun、PGLite 或 PostgreSQL/pgvector

当前源码已确认具备 Markdown/page 摄取、内容哈希、CJK 分块、自定义 schema pack、混合检索、typed links、图遍历和检索 capture/replay。

关键源码：

- `references/gbrain/src/core/engine.ts`：在 GBrain 研究仓库中的统一引擎接口；
- `references/gbrain/src/core/types.ts`：Page、Chunk、SearchResult；
- `references/gbrain/src/core/import-file.ts`：文件摄取和索引；
- `references/gbrain/src/core/ingestion/types.ts`：公开摄取协议；
- `references/gbrain/src/core/search/hybrid.ts`：混合检索；
- `references/gbrain/src/core/chunkers/recursive.ts`：CJK-aware 分块；
- `references/gbrain/src/core/link-extraction.ts`：链接抽取；
- `references/gbrain/src/core/schema-pack/`：可扩展类型和关系；
- `references/gbrain/src/core/eval-capture.ts`、`src/commands/eval-replay.ts`：检索回放。

以上路径均相对于 `../gbrain-llm-wiki-research/`。

## 4. 推荐技术架构

```text
原始 PDF / 图片 / DOCX / PPTX / XLSX
  │
  ├─ 原文件及哈希（业务文件存储）
  ▼
已部署 MinerU 3.4.4
  │  ZIP/JSON: md + content_list + middle_json + images
  ▼
MinerU Result Adapter
  │  下载、校验、解包、JSON 解码、资产登记、错误分类
  ▼
Canonical Document Builder
  │  document/version/units/nodes/tables/assets/anchors/relations/quality
  ▼
Canonical Document Store（基础文档主数据）
  ├─ Document Query Port → 后续合同/标书算法
  ├─ Fixture Export → 算法实验和回归
  └─ GBrain Projection Builder
       │  page/section Markdown + frontmatter + typed links
       ▼
     独立 GBrain Source
       ├─ keyword/vector/hybrid search
       ├─ graph traversal
       └─ retrieval capture/replay/eval
```

核心原则：**Canonical Document 是基础文档主数据；GBrain 是可重建的派生知识索引。**

## 5. P0-1：MinerU 服务调用适配器

### 5.1 适配器职责

1. 接收本地文件、文件流或已授权 URL。
2. 计算源文件 SHA-256、媒体类型和稳定 `document_id`。
3. 调用 `/tasks` 或 `/v1/process`。
4. 保存 MinerU `task_id/job_id` 和提交参数快照。
5. 轮询状态或处理回调，支持超时、取消和失败分类。
6. 下载 ZIP 或接收 JSON 结果。
7. 校验文件大小、ZIP 结构、必需文件和 JSON 可解析性。
8. 解码 JSON 字符串字段，拒绝静默吞掉非法 JSON。
9. 登记 Markdown、content list、middle JSON、图片和原始 ZIP 的哈希。
10. 把验证后的 `MinerUResultBundle` 交给 Canonical Builder。

### 5.2 接口选择

| 场景 | 首选接口 | 原因 |
|---|---|---|
| 批量/大文档 | `/tasks` | 异步、可查询、避免长连接 |
| 兼容现有业务 | `/v1/process` | 保持已有 job/callback 合同 |
| 小样例调试 | `/file_parse` | 调试简单，不用于批量主路径 |

首期优先支持 ZIP；图片较多时 JSON Base64 返回体过大。提交时至少请求 `return_md`、`return_middle_json`、`return_content_list` 和 ZIP 响应。

### 5.3 数据对象

```text
ParseRequest
  document_id / source_uri / local_file / source_sha256 / media_type
  backend / effort / language / requested_outputs / idempotency_key

ParseJob
  parse_id / mineru_task_id / compat_job_id / status
  submitted_at / finished_at / request_snapshot / error

MinerUResultBundle
  markdown / content_list / middle_json / assets[]
  raw_bundle_ref / artifact_hashes / parser_version
```

### 5.4 幂等与版本

```text
idempotency_key = sha256(
  source_file_hash + parser_profile + backend + effort
  + requested_outputs + adapter_version
)
```

同一键成功时可以复用结果；Parser、模型、effort 或 adapter 变化时生成新 `parse_id`，不覆盖旧结果。

### 5.5 错误分类

至少区分 `source_unavailable`、`unsupported_media_type`、`submit_failed`、`task_timeout`、`parse_failed`、`result_download_failed`、`invalid_zip`、`missing_required_artifact`、`invalid_content_list_json`、`invalid_middle_json`、`asset_missing` 和 `normalization_failed`。

## 6. P0-2：Canonical Document 基础文档数据

### 6.1 原则

- Parser-neutral、Versioned、Provenance-first、Location-aware；
- 同一解析版本内 stable IDs；
- 保留标题、段落、列表、表格、图片、公式和关系；
- 图片和大对象使用资产引用；
- 保留原始结果包引用和哈希；
- 无法精确定位时降级，不能伪造 bbox。

### 6.2 顶层对象

```text
CanonicalDocument
  schema_version
  canonical_document_id
  source
  parse
  renderings[]
  logical_units[]
  nodes[]
  relations[]
  tables[]
  assets[]
  chunks[]
  quality
  warnings[]
  artifacts
```

### 6.3 基础 Node

```text
DocumentNode
  node_id / parent_id
  type / subtype / order
  content.text / normalized_text / html / latex
  source_anchor
  asset_refs[]
  confidence
  provenance.raw_output / raw_path
```

Node 只表达文档事实，不增加 `contract_clause`、`tender_requirement` 等领域类型。领域对象以后通过 `source_node_ids` 引用它。

### 6.4 SourceAnchor

| kind | 定位内容 | 首期策略 |
|---|---|---|
| `page_bbox` | rendering、page、坐标空间、bbox/polygon | PDF/图片正式支持 |
| `docx_anchor` | part、section、paragraph/run/char | 先允许逻辑块降级 |
| `pptx_shape` | slide、shape、text range | 先允许 slide/块级降级 |
| `xlsx_range` | sheet、cell/range | 优先逻辑单元格定位 |
| `logical_block` | raw path、上下文 node | 无精确锚点时使用 |

### 6.5 Table、Asset 和 Chunk

`Table` 保留行列、rowspan/colspan、cell 内容、整表/cell anchor 和跨页关系。

`Asset` 保留类型、媒体类型、哈希、尺寸、存储 URI、来源 node 和 ZIP 原始路径。

`DocumentChunk` 是算法输入投影，包含 `chunk_id`、text、heading path、`source_node_ids`、source ranges、chunker name/version。先生成 node 再 chunk；更新 chunker 只生成新投影。

## 7. P0-3：Canonical Builder

```text
MinerUResultBundle
  → artifact validation
  → content_list/middle_json decode
  → asset inventory
  → logical unit normalization
  → deterministic node IDs
  → node/table/figure/formula conversion
  → relation/reading-order construction
  → anchor normalization
  → chunk projection
  → quality checks
  → schema validation
  → immutable CanonicalDocument
```

### 7.1 确定性 ID

```text
document_id = 稳定业务 ID 或源文件 hash
parse_id = hash(parse config + parser/model/adapter versions)
node_id = hash(parse_id + raw artifact + raw path + normalized type)
asset_id = hash(asset bytes)
chunk_id = hash(parse_id + chunker version + source_node_ids + normalized text)
```

数组序号不能单独作为永久身份。

### 7.2 纯确定性质量检查

- 必需产物存在且 JSON 可解析；
- node 数量、非空文本比例、页码范围和 bbox 合法；
- 阅读顺序没有重复/断裂；
- asset 引用存在；
- table 行列和 span 合法；
- chunk 完整映射到 node；
- node 带 provenance；
- Canonical JSON 通过 Schema。

质量结果只说明解析数据完整性，不判断合同或招标内容。

## 8. P0-4：稳定访问接口

```python
class DocumentRepository(Protocol):
    def get_document(document_version_id: str) -> CanonicalDocument: ...
    def get_nodes(node_ids: list[str]) -> list[DocumentNode]: ...
    def get_chunk(chunk_id: str) -> DocumentChunk: ...
    def list_chunks(document_version_id: str) -> list[DocumentChunk]: ...
    def resolve_evidence(refs: list[str]) -> list[SourceAnchor]: ...
    def get_asset(asset_id: str) -> AssetRef: ...

class DocumentParser(Protocol):
    def submit(request: ParseRequest) -> ParseJob: ...
    def wait(job_id: str) -> ParseJob: ...
    def fetch_result(job_id: str) -> MinerUResultBundle: ...

class KnowledgeIndex(Protocol):
    def index_document(document_version_id: str) -> IndexReceipt: ...
    def remove_document(document_version_id: str) -> None: ...
    def search(query: str, scope: SearchScope) -> list[EvidenceHit]: ...
```

这三个接口把 MinerU、Canonical 数据和 GBrain 隔离开。

## 9. P0-5：GBrain 融合判断

### 9.1 可直接利用

| 技术需求 | GBrain 能力 | 判断 |
|---|---|---|
| Markdown/文本摄取 | `import-file.ts`、公开 ingestion 协议 | 可做 adapter/skillpack PoC |
| page + frontmatter | `PageInput`、hash、source path | 可保存投影元数据 |
| 文档切块 | CJK-aware chunker | 可作对照基线 |
| 混合检索 | keyword/vector/RRF/reranker/graph | 适合作检索基座 |
| 知识关系 | typed links、graph traversal | 可表达确定性派生关系 |
| 自定义类型 | schema pack、开放 PageType | 可定义技术页面类型 |
| 轻量试验 | PGLite | 适合本机 PoC |
| 检索评测 | capture/export/replay | 可复用框架和思路 |

### 9.2 不能替代

| 需求 | 限制 | 方案 |
|---|---|---|
| 版面文档主数据 | Page/Chunk 没有完整 bbox/table cell 模型 | Canonical 独立保存 |
| 精确 SourceAnchor | SearchResult 主要返回 page/chunk | adapter 映射回 Canonical |
| 业务事务数据 | 页面不适合审批/状态事务 | 领域阶段另建 |
| 规则引擎 | schema pack 不是领域规则执行器 | 延期自建 |
| 中文自动关系 | mention/entity 路径仍有 ASCII 假设 | 首期写确定性 links |
| 中文关键词 | PGLite 为 ILIKE 降级；Postgres 需 FTS 配置 | 真实中文查询验证 |
| 领域评测 | replay 只测检索稳定性 | 本仓独立指标 |

### 9.3 接入方式

1. **CLI/文件 source PoC（首选）**：生成版本化 Markdown，调用 GBrain import/sync。
2. **MCP/Operation adapter**：封装 `put_page/get_page/search`，验证在线增量。
3. **TypeScript library adapter**：控制力强但绑定上游接口。
4. **Fork GBrain**：当前不做。

首期采用第 1 种，必要时增加第 2 种；Python 代码不直接引用 GBrain 内部 TypeScript 文件。

## 10. Canonical 到 GBrain 的投影

### 10.1 页面粒度

```text
documents/<document_id>/index.md
documents/<document_id>/sections/<id>.md
documents/<document_id>/tables/<id>.md
```

不把几百页文档放入单 page，也不提前切成无业务边界的小 token 块。

### 10.2 Frontmatter

```yaml
---
type: document-section
title: 第一章 项目概述
document_id: doc-001
document_version_id: doc-001@parse-003
canonical_node_ids: [p0001-b0001, p0001-b0002]
page_start: 0
page_end: 1
source_hash: "..."
parser: mineru
parser_version: 3.4.4
canonical_schema_version: "1.0"
projection_version: "0.1.0"
---
```

### 10.3 Source 与关系

建议 source：`parsed-documents`、`approved-materials`、`technical-notes`、`open-source-evidence`。不要为每个文件创建 source。

首期只写确定性关系：document contains section、section contains table、section follows section、projection derived_from document_version。

### 10.4 EvidenceHit

```text
EvidenceHit
  score / index_backend / source_id
  page_slug / gbrain_chunk_id / text
  document_version_id / canonical_node_ids[]
  source_anchors[]
  ranking_explanation
```

GBrain 命中通过 Canonical Repository 展开来源锚点；后续算法只依赖 `EvidenceHit`。

## 11. GBrain 技术 PoC

### 11.1 数据与对照

- 10 份数字 PDF、5 份扫描 PDF、5 份 DOCX；
- 只使用公开或脱敏样例；
- 比较简单 lexical、GBrain keyword-only、GBrain hybrid；
- 可选 Postgres/pgvector 和 reranker。

### 11.2 非领域查询集

精确标题/编号、明确短语、同义表达、表格字段、跨章节关系、零结果查询以及中文/数字/英文缩写混合查询。

### 11.3 指标

Recall@5、MRR@10、nDCG@10、正确 node 覆盖率、SourceAnchor 展开率、零结果准确率、索引/查询时延、索引体积、模型成本以及更新/删除一致性。

### 11.4 通过条件

- 索引页全部映射回 `document_version_id`；
- 命中全部解析出 canonical node 或明确标记页面级命中；
- 同版本更新不重复，新 parse 版本不覆盖旧版；
- 删除投影后无旧结果；
- 中文查询有可说明结果；
- 不修改 GBrain 上游源码完成首轮 PoC。

## 12. 开源技术积累方式

| 项目 | 积累目标 | 融合方式 | 暂不做 |
|---|---|---|---|
| MinerU | 解析结果、定位、表格/资产 | 正式 Python adapter | 不重建解析器 |
| GBrain | 摄取、检索、图、检索评测 | 独立 source + adapter PoC | 不作业务 DB，不启用 dream |
| OpenContracts | parser 插件、span/标注、版本模型 | 代码阅读 + 小 spike | 不部署完整平台 |
| 易标 OpenBidKit | 后台任务、工作区、导出、查重 | 隔离运行和接口研究 | AGPL 未决前不复制核心代码 |
| VerveDocs | DOCX 解析、编辑、导出保真 | 独立前端 PoC | 不接当前协作鉴权 |
| Presidio | PII 识别框架 | 独立实验 | 不宣称中文全检出 |
| Docling | 解析回归对照 | 固定样例离线比较 | 不建第二解析栈 |
| CUAD/ContractNLI | 数据格式和指标参考 | 暂存源码 | 领域任务延期，不训练 |

规则：固定 URL/commit/许可证；优先 adapter/CLI/MCP/公开 API；AGPL 与自研保持仓库和进程边界；升级重跑固定样例；每个 PoC 输出“能复用、需改造、不能复用”。

## 13. 建议代码结构

```text
src/contract_bid_research/
  document/
    models.py
    schema/
    ids.py
    quality.py
    chunking.py
  adapters/
    mineru/
      client.py
      result_bundle.py
      zip_reader.py
      normalizer.py
    gbrain/
      projection.py
      client.py
      mapping.py
  retrieval/
    interfaces.py
    lexical_baseline.py
    evaluation.py
  evaluation/
    metrics.py
    datasets.py
    reports.py
tests/fixtures/
  mineru/
  canonical/
  gbrain_projection/
```

真实客户文件、解析大包、数据库和 embedding 缓存放在被忽略的 `artifacts/` 或 `data/`；仓库只保留小型脱敏 fixture。

## 14. 技术任务清单

### T0：冻结协议

`CanonicalDocument v1`、`SourceAnchor v1`、三个稳定接口、ID 和版本规则。

### T1：MinerU adapter

`/tasks`、`/v1/process` client，ZIP/JSON reader，错误分类、幂等、超时和 fake client。

### T2：Canonical Builder

content list → node；middle JSON → provenance；images → asset；PDF bbox；chunk/node 映射；Schema 和质量测试。

### T3：GBrain projection

document/section/table Markdown、frontmatter、确定性 links、source 初始化、更新/删除/重建。

### T4：GBrain retrieval adapter

`KnowledgeIndex.search`、SearchResult → EvidenceHit、Anchor 展开和中文查询回归。

### T5：检索评测

20 份固定文档、50～100 条非领域查询、lexical/keyword/hybrid 对照和错误分类。

### T6：开源技术 spike

OpenContracts parser 对照、易标任务/导出/查重边界、VerveDocs 复杂 DOCX、Presidio 中文 recognizer。

## 15. 明确延期

### 15.1 模型网关和 Prompt 注册表

延期。GBrain PoC 如需 embedding/reranker，使用其自身 provider 配置；出现两个以上稳定算法调用方后再定义公共模型接口。

### 15.2 审计、安全、权限和可观测性

延期。本阶段只使用公开/脱敏样例和隔离环境，不建设生产多租户、OAuth、审计中心、告警、SLO、PITR 和容量规划。代码仍不得写入真实凭据或客户文档。

### 15.3 领域任务和产品功能

延期。已有领域任务和产品功能文档只作未来参考，不作为当前 backlog 或验收范围。

## 16. 实施顺序

```text
CanonicalDocument/SourceAnchor Schema
  → MinerU fake fixture + Builder
  → 真实 MinerU 小样例
  → Canonical → GBrain projection
  → GBrain PGLite keyword/hybrid
  → EvidenceHit → SourceAnchor 回跳
  → 固定查询集和检索评测
  → 再选下一项开源技术 spike
```

先打通 MinerU—Canonical—GBrain—Evidence 最小闭环，不同时部署全部项目。

## 17. 验证计划

- 单元：坏 ZIP、缺文件、坏 JSON、空结果、非法 bbox、ID、Schema、关系、资产和 chunk 映射。
- 集成：数字 PDF、扫描 PDF、DOCX 各一份，从 `/tasks` 到 Canonical 再到 GBrain。
- 证据：查询命中能回到原始 node/page/bbox；新旧 parse 版本并存。
- 回归：MinerU、adapter、chunker、GBrain 或 embedding 变化时比较 node 数、文本哈希、anchor 覆盖和检索指标。

## 18. 风险与替代

- GBrain 上游变化快：固定提交并通过 `KnowledgeIndex` 隔离。
- 中文关键词效果不足：保留 lexical baseline，同集比较 PGLite CJK、Postgres FTS 和 dense。
- GBrain 引用不够精确：只做候选召回，证据始终从 Canonical 展开。
- Canonical 首版过大：先实现 PDF/图片常用 node/table/asset/bbox/chunk，Office 降级。
- 项目能力重复：GBrain 先承担检索试验，暂不重复部署 OpenContracts 检索栈。

## 19. 最终判断

GBrain 可以用于知识投影摄取、混合检索、关系图、轻量存储试验和检索评测，但不能替代 MinerU 结果标准化、Canonical Document、SourceAnchor、业务状态、规则和领域评测。

当前正确积累路径：

```text
MinerU 已有服务
  + 自研 Canonical Document Adapter（必须建立）
  + 自研稳定接口与证据映射（必须建立）
  + GBrain 派生索引 Adapter（优先 PoC）
  + 开源组件独立 spike（按需）
  + 固定 fixtures/metrics/regression（持续积累）
```

完成这个闭环并得到评测结果后，再重新讨论领域任务、模型网关、产品功能和生产治理。

## 20. 待确认

1. 首个实现是否只正式支持 PDF/图片，Office 先降级。
2. GBrain PoC 先用 PGLite，还是直接使用 PostgreSQL/pgvector。
3. Canonical 样例是否从 MinerU 现有脱敏测试文件中选取。
4. GBrain PoC 先 keyword-only，还是允许使用现有 embedding provider。

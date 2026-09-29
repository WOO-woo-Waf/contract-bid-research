# 合同审核与标书撰写技术基础设施：实施与真实验证状态

形成日期：2026-08-11  
代码位置：本仓库（`contract-bid-research`）  
当前阶段：技术积累与基础设施验证

## 1. 结论

本仓已经形成一条可运行、可测试、可容器迁移的文档与知识基础链路：

```text
原始文件
  -> MinerU 公网 /tasks 文件流适配器
  -> ZIP 校验、安全解包、产物哈希
  -> Canonical Document 基础文档数据
  -> SQLite 关键词 / 向量 / 混合检索 / 重排
  -> GBrain Markdown 投影 / PGLite / typed links / graph
  -> Canonical chunk / node / page / bbox 证据回链
```

真实模型 API、真实 embedding、真实 rerank、SQLite 检索、GBrain PGLite 摄取和 Docker 内运行均已通过验证。MinerU 公网端点的客户端、文件流、轮询、下载和结果处理代码已完成，但公网 Ingress 当前返回自签名假证书，严格 TLS 在上传前终止，因此 MinerU 真实端到端解析尚未通过。不能用 `verify=False` 或 `-k` 绕过。

## 2. 当前范围与非目标

### 2.1 当前范围

- 外部解析服务适配及稳定错误分类；
- parser-neutral 的 Canonical Document；
- 真实 embedding、rerank、关键词/向量/混合检索；
- GBrain 的独立 PGLite、Markdown 摄取、typed link、图遍历与证据回链；
- 面向对象协议、CLI、单元测试、确定性 smoke fixture；
- 无密钥镜像和可迁移的 Docker/Compose 运行边界；
- 为后续合同审核和标书撰写算法提供稳定扩展点。

### 2.2 本阶段明确不做

- 不调研或固化合同审核、标书撰写的领域知识和任务分类；
- 不定义最终产品功能分区；
- 不建设统一模型网关和 Prompt 注册表；
- 不建设多租户、权限、审计、安全运营、生产可观测性；
- 不给出法律结论，也不把 AI 输出视为法律意见；
- 不修改 `../mineru-api-docker-upgrade`、`../gbrain-llm-wiki-research` 或 `references/` 中的第三方源码。

这些延期项不妨碍当前基础数据和算法适配器被后续业务复用。

## 3. 设计原则

1. **Canonical 是主数据，索引是派生数据**：原始文件及 Canonical JSON 可重建 SQLite/GBrain，不能反向依赖 GBrain 作为唯一事实源。
2. **证据优先**：检索结果必须携带 `canonical_document_id`、`chunk_id`、`node_ids` 和 `SourceAnchor`。
3. **不伪造位置**：有页码和 bbox 时保存 `page_bbox`；只有页码时保存 `page`；都没有时降级为 `unknown`。
4. **稳定且可版本化**：文档 ID 包含源文件、解析信息、Markdown、content list 哈希和 builder 版本；解析结果变化会形成新版本。
5. **依赖倒置**：未来算法依赖协议和 Canonical 数据，不直接依赖 MinerU HTTP 响应、SQLite 表或 GBrain CLI。
6. **密钥只在运行时**：`.env` 被 Git 和 Docker build context 排除，镜像不包含 API key 或客户数据。
7. **真实调用与离线测试并存**：单元测试使用 fake transport；live smoke 使用真实 API，但运行产物全部进入被忽略目录。

## 4. 代码结构与职责

```text
src/contract_bid_research/
├── config.py                 # 强类型配置、严格 dotenv、脱敏快照、旧格式迁移
├── protocols.py              # DocumentParser/Repository/KnowledgeIndex/ReviewRule
├── cli.py                    # 薄 CLI，只编排对象，不复制核心算法
├── adapters/
│   └── mineru.py             # MinerU /tasks 文件流和 ZIP 适配
├── document/
│   ├── models.py             # CanonicalDocument/Node/Chunk/Asset/SourceAnchor
│   ├── ids.py                # SHA-256 和稳定 ID
│   ├── builder.py            # MinerU content list -> Canonical
│   └── repository.py         # 不可变 JSON 文档仓库
└── knowledge/
    ├── models.py             # EvidenceHit/RerankResult
    ├── model_api.py          # OpenAI-compatible embedding + /rerank
    ├── sqlite_index.py       # FTS5、中文 bigram、cosine、RRF、rerank
    ├── projection.py         # Canonical -> GBrain Markdown/frontmatter
    └── gbrain.py             # 隔离 GBRAIN_HOME 的 GBrain CLI adapter
```

核心对象关系：

| 对象/协议 | 稳定职责 | 可替换实现 |
|---|---|---|
| `DocumentParser` | 文件转换为 Canonical Document | 当前 `MinerUClient`，以后可接 Docling/本地 MinerU |
| `DocumentRepository` | 保存和加载不可变文档版本 | 当前 `JsonDocumentRepository`，以后可接对象存储/数据库 |
| `KnowledgeIndex` | 索引和返回证据型命中 | 当前 `SQLiteKnowledgeIndex`，GBrain 为独立派生层 |
| `ReviewRule` | 后续审核算法扩展点 | 当前只定义协议，不沉淀领域规则 |
| `ModelAPIClient` | embedding/rerank 的单一模型边界 | 当前 Maas OpenAI-compatible API |
| `GBrainAdapter` | 通过固定版本公开 CLI 访问 GBrain | PGLite 当前已验证，可换 PostgreSQL |

## 5. MinerU 公网文件流基础设施

### 5.1 已实现调用流程

`MinerUClient` 使用严格 TLS 和 `httpx` 流式 multipart 文件提交：

1. `POST /tasks`，文件字段为 `files`；
2. 表单请求 Markdown、middle JSON、content list、图片和 ZIP 响应；
3. `GET /tasks/{task_id}` 轮询；
4. `GET /tasks/{task_id}/result` 下载 ZIP；
5. 原子保存到 `artifacts/mineru/<task_id>/result.zip`；
6. 校验 ZIP、Markdown、content list、middle JSON 和图片；
7. 构建 Canonical Document 并写入文档仓库。

默认解析参数是 `language=ch`、`backend=vlm-engine`、`effort=high`、`parse_method=auto`，公式、表格和图片分析开启。参数对象是不可变 `ParseOptions`，以后可以由调用方显式构造不同 profile。

### 5.2 结果安全和完整性

- 拒绝绝对路径和包含 `..` 的 ZIP member，防止路径穿越；
- Markdown 必须为 UTF-8；
- content list 必须是 JSON list，兼容 `{ "content_list": [...] }` 包装；
- middle JSON 存在时必须可解析；
- 图片按媒体类型登记为 `Asset`；
- 保存 ZIP、Markdown、content list、middle JSON 的 SHA-256；
- ZIP 原始包和 Canonical JSON 分层存储，索引可从 Canonical 重建。

### 5.3 稳定错误分类

当前至少覆盖：

```text
source_unavailable
submit_failed
status_failed
task_timeout
parse_failed
result_download_failed
tls_verification_failed
invalid_zip
missing_required_artifact
invalid_markdown
invalid_content_list_json
invalid_middle_json
```

### 5.4 当前外部阻塞

2026-08-11 使用真实 PDF `../mineru-api-docker-upgrade/demo/pdfs/demo1.pdf` 调用：

```json
{
  "status": "error",
  "category": "tls_verification_failed"
}
```

现场证书为 Kubernetes Ingress fake certificate：

```text
subject/issuer: O=Acme Co, CN=Kubernetes Ingress Controller Fake Certificate
SAN: DNS:ingress.local
expected host: mineru.example.invalid
SHA-256 fingerprint:
1A:13:98:B9:FD:3B:D3:7D:1E:F6:3F:2B:E0:8A:CF:5E:0F:2E:0B:70:87:89:A6:51:FB:23:2D:B8:18:A1:02:53
```

修复要求：Ingress 绑定由受信任 CA 签发、SAN 包含 `mineru.example.invalid` 的证书。修复后无需改代码，重跑 `parse` 即可。若服务使用内部 CA，可通过 `MINERU_CA_BUNDLE` 显式提供 CA 文件；它不是关闭校验的开关。

## 6. Canonical Document 基础数据

### 6.1 顶层结构

```text
CanonicalDocument
├── schema_version
├── canonical_document_id
├── source: file_name/media_type/sha256/size
├── parse: parser/version/backend/task_id/artifact_hashes/parsed_at
├── markdown
├── nodes[]
├── chunks[]
├── assets[]
├── warnings[]
└── quality
```

`DocumentNode` 保存类型、顺序、原文、规范化文本、来源锚点、资产引用、置信度和 provenance。`DocumentChunk` 只是一种算法投影，保存包含它的 node IDs 和所有 anchors。

### 6.2 稳定 ID

- `canonical_document_id`：源文件哈希 + parser/version/backend + 解析产物哈希 + Markdown 哈希 + content list 哈希 + builder 版本；
- `node_id`：document ID + order + type + normalized text + anchor；
- `chunk_id`：document ID + chunk order + node IDs + text；
- `asset_id`：资产路径 + 资产内容哈希。

这样可避免“Parser 输出已经变化，但旧 ID 没变”的静默污染。当前 builder 为 `canonical-builder-v1`；数据结构重大变化时应提升 schema/builder 版本，不覆盖历史文档。

### 6.3 位置模型

| `kind` | 使用条件 | 核心字段 |
|---|---|---|
| `page_bbox` | 页码和合法 bbox 均存在 | page index、四点 bbox、坐标空间、raw path |
| `page` | 只有合法页码 | page index、raw path |
| `logical` | 未来 Office 逻辑位置 | raw path/逻辑位置 |
| `unknown` | 无可靠位置 | raw path，不伪造坐标 |

坐标最大值不超过 1000 时标为 `bbox_1000`，否则保留 `parser_native`。

## 7. 可移植 SQLite 知识库

### 7.1 索引内容

SQLite 同时保存：

- 文档 source/parse/schema 元数据；
- chunk 原文；
- 中文 bigram 和英文/数字 token；
- `text-embedding-v3` 的 float32 向量；
- Canonical node IDs 和 anchors；
- FTS5 表及文档/分块索引。

数据库使用 WAL，默认位于 `runtime/knowledge.sqlite3`，容器中位于 `/data/knowledge.sqlite3`。

### 7.2 检索模式

| 模式 | 算法 | 适用验证 |
|---|---|---|
| `keyword` | FTS5 + 中文 bigram + 查询词覆盖率 | 精确术语、编号、名称 |
| `vector` | 真实 query embedding + numpy cosine | 同义改写和语义问题 |
| `hybrid` | keyword/vector 候选 + RRF | 通用召回基线 |
| rerank | `qwen3-rerank` `/v1/rerank` | 对候选前几名重新排序 |

关键词覆盖率用于修复 FTS/BM25 长度归一化把短但只命中少量词的 chunk 错误置顶。每个返回项都是 `EvidenceHit`，不是裸字符串。

## 8. GBrain 融合

### 8.1 可复用能力

当前固定使用：

```text
repository: ../gbrain-llm-wiki-research/references/gbrain
commit: 3fafb69b077e602e1286af9cb092ed94455657a8
version: 0.42.66.0
runtime: Bun 1.3.14
storage: isolated PGLite under GBRAIN_HOME
```

本仓没有复制或修改 GBrain 源码，而是通过公开 CLI/call 操作封装 adapter。

### 8.2 投影规则

每个 Canonical 文档生成：

- 1 个 document Markdown page；
- 每个 Canonical chunk 生成 1 个 chunk Markdown page；
- frontmatter 记录 document/chunk/node IDs、source anchors 和 tags；
- 每个 chunk 建立一条 `chunk --derived_from--> document` typed link；
- GBrain 命中通过 slug 重新映射到 Canonical chunk 和原始 anchors。

GBrain 会遵守外层仓库 `.gitignore`，而 `artifacts/` 本来就应忽略。adapter 导入时把投影复制到工作树外的临时目录，保留相对 slug 后再执行 import，避免出现“生成了投影但导入 0 文件”。

### 8.3 检索配置边界

GBrain 配置为 `search.mode=conservative` 且关闭自带 reranker。原因是：

- GBrain 负责 Markdown/PGLite/keyword/vector/hybrid recall 和 graph；
- 本仓已经通过真实 `qwen3-rerank` 统一验证重排；
- 不需要 ZeroEntropy key，也避免双重 rerank。

`gbrain doctor` 当前总分 90、brain checks 100、schema 125/latest。两个 warning 不阻塞本阶段：历史 ZeroEntropy 认证失败记录，以及未配置 Anthropic subagent；当前未使用 GBrain agent/dream/autopilot。

## 9. 配置与密钥契约

`.env.example` 是可审查契约，`.env` 是本机私密状态。`config-check` 只输出 `<set>/<missing>`，不会输出 key。

| 变量组 | 关键变量 | 说明 |
|---|---|---|
| MinerU | `MINERU_BASE_URL`、`MINERU_TOKEN`、`MINERU_CA_BUNDLE` | TLS 永远开启；token 可为空取决于服务端 |
| Model API | `MODEL_API_BASE_URL`、`MODEL_API_KEY` | 当前真实 base 为 `https://model-api.example.invalid/v1` |
| Embedding | `EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS` | 当前 `text-embedding-v3`、1024 |
| Rerank | `RERANK_MODEL` | 当前 `qwen3-rerank` |
| Storage | `CONTRACT_BID_*` | Canonical/artifacts/SQLite 路径 |
| GBrain | `GBRAIN_REPOSITORY`、`GBRAIN_HOME` | 固定源码位置与隔离 PGLite home |

旧 `.env` 若只有两行 URL/token，可运行一次：

```bash
rtk conda run -n contract-bid-research contract-bid-infra config-migrate
```

迁移是原子写入，并把文件权限设为 `0600`。

## 10. CLI 使用

### 10.1 环境与基础检查

```bash
rtk conda env create -f environment.yml
rtk conda run -n contract-bid-research python -m pip install --no-deps -e .
rtk conda run -n contract-bid-research contract-bid-infra config-check
rtk conda run -n contract-bid-research contract-bid-infra model-smoke
```

### 10.2 文档解析和知识索引

```bash
rtk conda run -n contract-bid-research contract-bid-infra parse /path/to/input.pdf
rtk conda run -n contract-bid-research contract-bid-infra kb-index data/canonical/<document-id>.json
rtk conda run -n contract-bid-research contract-bid-infra kb-search "原文证据在哪里" --mode vector
rtk conda run -n contract-bid-research contract-bid-infra kb-search "编号和来源锚点" --mode hybrid
```

### 10.3 GBrain

```bash
rtk conda run -n contract-bid-research contract-bid-infra gbrain-init
rtk conda run -n contract-bid-research contract-bid-infra gbrain-import data/canonical/<document-id>.json
rtk conda run -n contract-bid-research contract-bid-infra gbrain-search "来源锚点" --limit 5
rtk conda run -n contract-bid-research contract-bid-infra gbrain-evidence data/canonical/<document-id>.json "如何定位原文"
rtk conda run -n contract-bid-research contract-bid-infra gbrain-graph documents/<document-id>/chunks/<chunk-id> --depth 2
rtk conda run -n contract-bid-research contract-bid-infra gbrain-stats
rtk conda run -n contract-bid-research contract-bid-infra gbrain-doctor
```

`gbrain-graph` 参数必须是完整 GBrain slug，不是单独的 chunk ID。

## 11. Docker 和 Compose

### 11.1 镜像内容和边界

- Python 3.10 slim-bookworm；代码同时支持本机 Conda Python 3.11；
- Bun 1.3.14；
- 固定 GBrain commit；
- 非 root 用户 `10001:10001`；
- `/data` 保存数据库/PGLite，`/artifacts` 保存派生产物；
- `/inputs` 只读；
- 不 COPY `.env`、`artifacts/`、`runtime/`、`data/`、`references/`。

### 11.2 WSL 代理下构建

代理只监听 WSL `127.0.0.1:7897` 时，bridge 中的 `host.docker.internal` 不可达；使用单次 host-network build：

```bash
rtk proxy env \
  http_proxy=http://127.0.0.1:7897 \
  https_proxy=http://127.0.0.1:7897 \
  HTTP_PROXY=http://127.0.0.1:7897 \
  HTTPS_PROXY=http://127.0.0.1:7897 \
  no_proxy=localhost,127.0.0.1,::1,*.local \
  NO_PROXY=localhost,127.0.0.1,::1,*.local \
  docker build --network=host \
  --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
  --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
  --build-arg NO_PROXY=localhost,127.0.0.1,::1 \
  -t contract-bid-infra:20260811-local .
```

这些 build args 只有代理地址，不包含 API key。真实 key 只通过运行时 `--env-file .env` 或 Compose secret/config 注入。

### 11.3 Compose 使用

```bash
rtk docker compose config --quiet
rtk docker compose run --rm contract-bid-infra config-check
rtk docker compose run --rm contract-bid-infra model-smoke
rtk docker compose run --rm contract-bid-infra gbrain-init
```

`inputs/` 下除 README 外全部被 Git 忽略。容器使用 UID/GID `10001:10001`，宿主输入必须允许该身份读取。Canonical JSON 默认使用限制权限；私密文件应复制进访问受控的 volume 并转交 ownership，不建议简单改成 world-readable。

## 12. 真实验证结果

### 12.1 自动化测试

```text
python -m compileall -q src      PASS
pytest                           17 passed
git diff --check                 PASS
```

测试覆盖配置迁移/脱敏、Canonical 构建和稳定 ID、MinerU multipart/轮询/ZIP/TLS 错误、关键词/向量/RRF/rerank、GBrain evidence 映射和 graph 去重。

### 12.2 模型 API

真实 `https://model-api.example.invalid/v1`：

```text
model count             45
embedding model         text-embedding-v3
vectors                 2
dimensions              1024
rerank model            qwen3-rerank
expected first result   page + bbox source anchor
```

本机 Conda 与 Docker 容器内的 `model-smoke` 均通过。

### 12.3 SQLite 检索

确定性非领域 fixture 生成 1 个 Canonical Document、4 个 chunks，并完成真实 embedding：

- 关键词查询“来源锚点 边界框”：证据 chunk 第一，返回 page 0/1 和 `bbox_1000`；
- 向量查询“怎么定位回原文件证据”：证据 chunk 第一；
- 混合查询“知识库怎样组合关键词语义召回和重排”：检索说明 chunk 第一；
- qwen3-rerank 第一名 relevance score 约 `0.9438`。

运行库中可能保留多次 smoke 文档版本，因此统计总数可大于本次 fixture；算法验证以本次稳定 document/chunk IDs 和排名为准。

### 12.4 GBrain 本机和容器

本机及全新 Docker volume 的结果一致：

```json
{
  "page_count": 5,
  "chunk_count": 5,
  "embedded_count": 5,
  "link_count": 4,
  "pages_by_type": {"note": 5}
}
```

验证内容：

- 新 PGLite 初始化；
- 5 个 Markdown pages 首次导入，无错误；
- 真实 embedding 数量等于 chunk 数量；
- 4 条 `derived_from` 边；
- graph 深度 2 返回去重后的 4 条边；
- GBrain hit 映射回 Canonical node IDs、page index 和 bbox；
- 重复导入被识别为 unchanged，不重复创建 pages/chunks；
- doctor 的 embedding env 与数据库配置一致，search mode 为 conservative。

Docker 验证镜像：

```text
image ID       sha256:9734e3d7811fc490183dd24243f4183497917412ba12b2253d09f067fa44ba93
platform       linux/amd64
size           230,318,461 bytes
GBrain commit  3fafb69b077e602e1286af9cb092ed94455657a8
Bun             1.3.14
secret files   absent
```

用于容器 GBrain smoke 的临时 volume 已删除，未执行 prune，也未删除其他镜像、卷或容器。

## 13. 已知限制与风险

1. **MinerU E2E 未通过**：唯一硬阻塞是公网 Ingress 证书；客户端已正确拒绝。
2. **MinerU token 当前为空**：TLS 修复后若服务要求鉴权，还需在 `.env` 设置 `MINERU_TOKEN`。
3. **Canonical v1 是技术基线**：尚未表达复杂表格 cell、跨页关系、Office shape/range 等完整结构；不能伪装成已支持。
4. **SQLite 向量扫描是小规模基线**：当前 numpy 全扫描适合 PoC；数据量增加后应换 pgvector/Qdrant 等 ANN，但保持 `KnowledgeIndex` 协议。
5. **没有删除旧索引版本的 CLI**：研发阶段保留版本便于回归；后续需要显式生命周期策略。
6. **GBrain 为派生层**：不能存储唯一的 bbox/表格事实，也不能替代 Canonical 仓库。
7. **容器输入权限需管理**：非 root UID 不能读取宿主 root 的 `0600` 文件，部署时应通过 ownership/ACL 或受控 staging volume 解决。
8. **生产治理延期**：审计、安全运营、可观测性、配额、备份恢复和多租户均不属于当前验收。

## 14. 下一阶段建议

按技术积累优先级推进，不进入领域知识设计：

1. MinerU Ingress 修复后，立即用 PDF、扫描 PDF、DOCX 各完成一次公网 E2E，并保存脱敏指标而非业务文件；
2. 扩展 Canonical v1.1：表格/cell、图片与 caption、公式、Office 逻辑锚点、跨页关系；
3. 建立解析回归 fixture 集和 quality gate：node 数、anchor coverage、asset integrity、表格完整率；
4. 为 SQLite/GBrain 建立固定查询集和 Recall@K、MRR、nDCG、证据定位准确率；
5. 抽出 `EmbeddingProvider`、`Reranker` 和 `KnowledgeProjection` 协议，以便不改业务算法地替换存储/模型；
6. 给 Docker 增加离线依赖锁定和镜像 SBOM；目前固定了 GBrain/Bun，但 Python 依赖仍按范围解析；
7. 等基础数据和评测稳定后，再开始合同审核/标书撰写算法插件，不提前建设最终产品 UI。

## 15. 验收边界

当前可以判定为完成：

- 基础设施设计已落实为面向对象代码和 CLI；
- 模型、embedding、rerank、SQLite/GBrain 检索和证据回链均有真实验证；
- Docker 镜像可构建、可运行、无运行时密钥固化；
- MinerU 调用链已实现并正确执行严格 TLS；
- 外部证书问题被明确隔离，不通过不安全绕过伪造成功。

当前不能判定为完成：MinerU 公网真实解析闭环。它必须等服务端证书修复后重新验证。

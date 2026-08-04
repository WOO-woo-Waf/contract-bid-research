# 开源项目对比与二次开发建议

形成日期：2026-08-04

## 目标与评价维度

评价维度包括：源码可得性、固定版本、许可证、真实功能、可复现构建、领域匹配、隐私边界、二开成本和生产缺口。完整版本指纹见 `references/UPSTREAMS.md`。

## 对比结论

| 项目 | 定位 | 代码级/构建核验 | 推荐复用 | 主要约束 |
|---|---|---|---|---|
| MinerU 3.4.4（已有） | 统一文档解析 | 用户确认已部署；已有 API/Canonical JSON 设计 | **生产主解析器** | 自定义许可、TLS 信任链、Canonical 适配完成度需验收 |
| OpenContracts | 文档智能/标注/抽取平台 | MIT；Django/GraphQL/Postgres/pgvector/Celery + React；有权限、引用图、MCP、抽取 | **合同平台首选基座** | 体系较重；自带 telemetry 默认需关闭；接 MinerU 需写适配器 |
| 易标 OpenBidKit | 投标桌面工作流 | 技术方案/知识库/查重/废标有代码；本机 TypeScript/Vite 构建通过 | **投标任务设计和独立组件参考** | AGPL-3.0-only；NOTICE；无 lockfile；多项菜单未完成；存在出站链路 |
| VerveDocs | 在线 Office 编辑/协作 | Core、AI 插件、协作服务有代码；部分构建通过 | **Word 编辑器候选** | 无根 workspace；AI lock 过期；完整版 UI 在 Linux 被 Windows 专属依赖阻断；协作鉴权不足 |
| AI LegalComp | 宣传中的合同平台 | GitCC 源码未获得 | **暂缓** | 无法审计许可证、架构和宣传功能 |
| CUAD | 合同条款抽取数据/代码 | 快照含 510 份合同、41 类问题 | **算法基线和标签设计参考** | 英文；根许可证缺失，数据商用前需单独确认 |
| ContractNLI | 文档级合同 NLI | CC-BY-4.0；607 份 NDA、17 假设 | **符合性/冲突/证据任务参考** | 英文 NDA，领域窄，需署名和中文重标 |
| Docling | 多格式解析 SDK | MIT，活跃；固定 2.118.0 快照 | **后备/长尾/回归对照** | 已有 MinerU，不进首期主链；模型权重另审 |
| Presidio | PII 检测和脱敏 | MIT；规则、NER、正则、校验和、可扩展 recognizer | **研究数据脱敏组件** | 中文识别器和企业实体规则需自建；官方明确不保证全检出 |

## 易标源码分析

固定提交：`9e354bde0e2581fa8c47f08ec7c50f8ee82ab936`。

### 已确认能力

- Electron Main/Preload + React/TypeScript Renderer，本地 SQLite/文件工作区。
- 招标导入、标段识别、需求分析、目录、全局事实、正文生成、图片计划和 Word 导出任务。
- 文档知识库、标书查重、废标项检查、模板/导出设置。
- OpenAI-compatible 文本/生图接口，MinerU 精准/Agent 解析入口，OpenCode/Pi Agent 运行时。
- 后台任务、暂停/恢复、队列、重试、工作区落盘。

### 明确未完成或需降级描述

- 商务标和投标机会页面直接显示“尚未完成”。
- AI 评标、图片知识库等入口带“开发中”提示。
- “十万字约 1 元”是 README/文章个案，不是可复现实验结论。
- 最新提交删除 `package-lock.json`，`npm ci` 实测报错；按版本范围 `npm install --package-lock=false` 后构建才通过，依赖不再可复现。
- 构建产物主 JS 约 931 kB、Mermaid 等有多个大 chunk，桌面体验需要进一步启动和内存测试。

### 隐私事实

“配置/缓存/结果在本机”并不等于“没有出站”：

- 模型请求会把任务上下文发送到配置的模型 Base URL。
- MinerU 云 API 会上传待解析文件。
- 源码包含 `analytics.agnet.top` 的使用埋点、公告、许可证、插件/资源和 Agent 错误上报。
- 错误上报快照包含配置、运行信息、路径、任务上下文等对象，正式使用必须做字段级审计和默认关闭策略。

### 许可证建议

AGPL 允许商业使用，但修改后分发或提供网络交互服务可能触发对应源码提供义务，NOTICE 还要求保留归属。闭源产品不要直接复制核心代码后假定无义务。可选方案：

1. 将原项目作为独立 AGPL 客户端/服务，明确提供对应源码并完成法务审查。
2. 只研究公开任务流程、输入输出和 UI 思路，自主实现不复制表达性代码。
3. 与作者取得商业许可。

## VerveDocs 源码分析

固定提交：`f72f4850b3915538f90b3338c3f3554f508d8eef`，根许可证 MIT。

### 可复用点

- `@vervedoc/core` 提供文档元素、命令、历史、表格、图片、分页等核心。
- `@vervedoc/docx` 提供 Vue UI；Excel/PPT 是独立编辑模块。
- AI 插件只是选区润色、翻译、摘要、续写、扩写、语法和自定义请求，可作为编辑辅助，不是合同审核引擎。
- Yjs + Hocuspocus + MongoDB 协作服务具备基础持久化路径。

### 生产缺口

- 多个包独立版本和 lockfile，没有根 workspace；本地源码之间多依赖 npm 已发布版本，联调和原子发布困难。
- AI 插件的 package.json 与 lockfile 不一致，`npm ci` 失败；按范围安装后可构建。
- `vervedocs-docx` 把 `@esbuild/win32-x64` 放在普通 devDependency，Linux 安装报 `EBADPLATFORM`。
- 协作 token 是客户端可伪造的 `{userId,userName}` JSON，没有签名、会话验证或文档 ACL；注释中还依赖未随仓提供的 Spring Boot 服务。
- MongoDB 敏感词接口失败时选择保存未过滤内容，这不是合同隐私或合规防线。
- 需要真实复杂 DOCX 的导入/导出、批注、修订、域、页眉页脚和字体回归，README 功能列表不能替代兼容性测试。

建议先抽取 MIT core/docx 能力做技术验证；协作服务不要原样上线。

## OpenContracts 源码分析

固定提交：`401d38c00cade51cba84e73a1297e22a9d8ba620`，MIT。

适合作为合同基座的原因：

- 文档/语料库、标注标签、关系、抽取、对话和版本化模型已经成熟。
- PDF/文本精确 span、PAWLS 布局数据、引用图符合“结论回到原文”的要求。
- 对象级权限、GraphQL、REST、MCP、Agent 工具和审计路径比宣传型合同项目完整。
- Parser/Embedder/Thumbnailer 可插拔，可增加 MinerU Canonical JSON parser 而不替换下游。
- 人工标注是 ground truth，适合持续建设中文合同和招标金标集。

需要控制：

- 完整部署包含 PostgreSQL/pgvector、Redis/Celery、Django、React 和解析微服务，运维成本高于桌面工具。
- README 说明默认有匿名 telemetry；后端设 `TELEMETRY_ENABLED=False`，前端不设置 PostHog Key。
- 默认面向通用文档，不带中国合同法规/playbook 和投标业务模型，这部分仍需自建。

## 数据与基础组件

- CUAD 适合建立 span 抽取基线，不能直接证明中文合同审核能力。
- ContractNLI 最值得借鉴的是“结论标签 + 证据 span”联合任务，而不是其固定 17 个 NDA 假设。
- Presidio 应位于训练/评测数据入库前；对姓名、手机号、身份证、统一社会信用代码、银行账号、地址、项目编号和企业内部编号增加中文 recognizer，并由人工抽样检查漏脱敏。
- Docling 只保留长尾格式、跨引擎回归和 MinerU 故障降级研究，避免重复生产化。

## 推荐组合

| 层 | 首选 | 说明 |
|---|---|---|
| 文档解析 | 现有 MinerU | 统一输出 Canonical JSON/SourceAnchor |
| 合同语料与标注 | OpenContracts | 增加 MinerU parser adapter 和合同领域 schema |
| 合同算法 | 规则 + 混合检索 + NLI/LLM | CUAD/ContractNLI 只做任务/指标参考 |
| 投标工作流 | 自研领域层，参考易标 | 若复用代码，先完成 AGPL 决策 |
| Word 编辑 | VerveDocs 技术验证 | 修复工程和安全问题后再选型 |
| 隐私 | Presidio + 自定义中文 recognizer | 配合内网模型、出站控制和审计 |
| 解析备选 | Docling | 不进入首期生产主链 |

## 验证计划

1. OpenContracts 仅做最小本地部署和 MinerU 适配 spike，不先做全量定制。
2. VerveDocs 用 20 份真实复杂 DOCX 做兼容性矩阵，并在 Linux/Windows CI 都构建。
3. 易标功能逐项跑固定招标样例，记录任务状态、模型成本、证据覆盖和导出质量。
4. 所有依赖保留 SBOM、固定版本和许可证快照；升级必须过回归门禁。

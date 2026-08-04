# Upstream source manifest

形成日期：2026-08-04（Asia/Shanghai）

本清单中的许可证和功能结论以固定提交的仓库内容为准；公众号文章只作为线索。

| 项目 | 上游地址 | 本地目录 | 固定提交 | 许可证 | 状态 |
|---|---|---|---|---|---|
| 易标 / OpenBidKit | <https://github.com/FB208/OpenBidKit_Yibiao> | `references/yibiao-simple/` | `9e354bde0e2581fa8c47f08ec7c50f8ee82ab936` | AGPL-3.0-only + NOTICE 归属要求 | 已拉取；旧地址重定向到同一仓库 |
| AI LegalComp | <https://www.gitcc.com/adrien/ai-legalcomp0878> | `references/ai-legalcomp0878/` | 未获得 | 无法核验 | 网页有 WAF，匿名 Git 要求凭据；未将文章宣传视为源码事实 |
| VerveDocs | <https://gitee.com/wanghe520/vervedocs> | `references/vervedocs/` | `f72f4850b3915538f90b3338c3f3554f508d8eef` | MIT | 已拉取 |
| OpenContracts | <https://github.com/Open-Source-Legal/OpenContracts> | `references/opencontracts/` | `401d38c00cade51cba84e73a1297e22a9d8ba620` | MIT | 已拉取 |
| CUAD | <https://github.com/The-Atticus-Project/cuad> | `references/cuad/` | `67faa0e6023b04fcaae6cc09497ab00e5d63a2a2` | 仓库无根许可证；部分代码有 Apache-2.0 头，数据条款需单独复核 | 已拉取 |
| ContractNLI | <https://github.com/stanfordnlp/contract-nli> | `references/contract-nli/` | `eced6528dd3c1d14d73f9a87df8f7bdbc03126f9` | CC-BY-4.0 | 已拉取 |
| Docling | <https://github.com/docling-project/docling> | `references/docling/` | `9b454c9e88454d95fd04d538c552a3c07bc3c04d` | MIT（模型权重另审） | 已拉取，仅作备选/对照 |
| Presidio | <https://github.com/data-privacy-stack/presidio> | `references/presidio/` | `6116c0685c7efb27c40daf90369afabb32c6b911` | MIT | 已拉取 |
| GBrain | <https://github.com/garrytan/gbrain> | 外部研究仓库 `/root/dev/gbrain-llm-wiki-research/references/gbrain` | `3fafb69b077e602e1286af9cb092ed94455657a8` | MIT | 已有完整源码与专项调研；作为知识投影、混合检索、图关系和检索评测 PoC 候选 |
| MinerU 生产解析基座 | `/root/dev/mineru-api-docker-upgrade` | 外部已有项目，不重复克隆 | `0dfc9460cd9ab693b9af60ae3fbffd7bc111b062`（本次只读观察） | 自定义 MinerU License，生产需履行条件 | 用户确认已部署；本机无运行容器，公网严格 TLS 探测受自签名证书阻断 |

## 复现

以下命令使用当前个人 GitHub 身份，只做只读克隆，不推送：

```bash
gh repo clone FB208/OpenBidKit_Yibiao references/yibiao-simple -- --depth 1
gh repo clone Open-Source-Legal/OpenContracts references/opencontracts -- --depth 1 --filter=blob:none
gh repo clone The-Atticus-Project/cuad references/cuad -- --depth 1 --filter=blob:none
gh repo clone stanfordnlp/contract-nli references/contract-nli -- --depth 1 --filter=blob:none
gh repo clone docling-project/docling references/docling -- --depth 1 --filter=blob:none
gh repo clone data-privacy-stack/presidio references/presidio -- --depth 1 --filter=blob:none
git clone --depth 1 https://gitee.com/wanghe520/vervedocs.git references/vervedocs
```

所有克隆均为研究快照。更新前先记录新提交、许可证变化、迁移说明和回归结果，不能直接追随默认分支进入生产。

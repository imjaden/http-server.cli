# http-server.cli 文档中心

本目录是 http-server.cli 仓库的**文档主题索引**：按主题定位现行 design/review/规范文档，文档本体
保留原位（Q1=A 窄幅归档决策：不做主题手册化，一次性过程文档中仅 superseded 文档归档）。

备注：本文档为仓库内导航索引，不进 vault 镜像；归档桶随 `docs@archive` 落地即自动停止 vault 镜像
（与 llm-radar documents/README.md 同约定）。

## 主题索引（原位保留）

| 主题 | 现行文档（定位） | 状态 |
|---|---|---|
| CLI 总览 / 启动 | [hs-cli-design-v1.0-20260624](hs-cli-design-v1.0-20260624.md)、[url-flag-design-v2.0-20250715](url-flag-design-v2.0-20250715.md)、[cli-json-output-design-v1.1-20260819](cli-json-output-design-v1.1-20260819.md)、[test-design-spec-v1.2-20260702](test-design-spec-v1.2-20260702.md) | 保留 |
| 书签系统 | [bookmark-feature-design-v1.1-20250715](bookmark-feature-design-v1.1-20250715.md)、[bookmark-multi-page-design-v1.1-20260819](bookmark-multi-page-design-v1.1-20260819.md) | 保留 |
| Web 服务注册（hs web） | review 闭环报告（CL001/CL002，见 `review/`）+ features.md Web 节；无独立 design | 保留 |
| HTTP 服务 / 性能 | [perf-hot-path-optimization-design-v1.1-20260722](perf-hot-path-optimization-design-v1.1-20260722.md)、[ports-detect-design-v1.1-20250716](ports-detect-design-v1.1-20250716.md)、[http-server-index-redesign-v1.0-20260825](http-server-index-redesign-v1.0-20260825.md)、[light-dark-theme-design-v1.0-20260706](light-dark-theme-design-v1.0-20260706.md)、[github-corner-link-design-v1.0-20260706](github-corner-link-design-v1.0-20260706.md) | 保留 |
| Dashboard | [hs-dashboard-design-v2.0-20260629](hs-dashboard-design-v2.0-20260629.md) | 保留 |
| MCP 集成 | [hs-mcp-design-v1.0-20260624](hs-mcp-design-v1.0-20260624.md) | 保留 |
| AI 对接 | [hs-ai-integration-design-v1.0-20260825](hs-ai-integration-design-v1.0-20260825.md) + review 链（Q4 保留：ai-integration-audit v1.0/v1.1、ai-interchange-settle-audit，见 `review/`） | 保留 |
| CI/CD 发布（现行） | [github-ci-cd-design-v1.1-20260701](github-ci-cd-design-v1.1-20260701.md)（.github/workflows/release.yml 现行实现依据） | 保留 |
| review 审计报告桶 | `review/`（CL001/CL002、HS-SEC 闭环、html-gen-optimize-suggestions Q2 保留原位等） | 保留 |
| 素材 / 交接 | `references/`（english-sentences、knowledge）、`handoff/`（.hermes-project.yaml 引用 handoff-http-server.cli-review.md） | 保留 |
| 治理面（仓库根，不在本目录） | `review-log.md`（append-only 审计日志）、`features.md`（功能清单事实源）、`http-server.cli.spec.yaml`（功能契约）、`.review-level.yaml`、`CHANGELOG.md` | 保留 |

## 归档口径（2026-09-08 docs@archive）

已 superseded 的一次性文档 3 份 → `documents/archive/root-20260908/`
（桶内清单以 `git ls-files documents/archive/root-20260908/` 为准）：

| 主题（原 documents/ 根，均已含版本日期命名） | 桶 | 归档理由 |
|---|---|---|
| pypi-release-checklist（2026-06-23） | `archive/root-20260908/` | 发布流程已由 scripts/release-*.sh + .github/workflows/release.yml 取代，历史事实由 CHANGELOG 承载 |
| pypi-release-steps（2026-06-24） | `archive/root-20260908/` | 同上（操作步骤 superseded） |
| github-ci-issues（2026-07-04） | `archive/root-20260908/` | 问题记录（过去导向），结论已并入 github-ci-cd-design + 现行 CI |

归档即停止 vault 镜像；其余 design/review/references 文档全部保留原位（Q1=A / Q2 / Q4 决策）。

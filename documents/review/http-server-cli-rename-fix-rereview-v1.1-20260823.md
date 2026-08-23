# http-server.cli 改名批次 — re-audit 复查报告 v1.1

> 日期: 2026-08-23
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 复查对象: 0dcbab2 (HS-SEC-011~015) + fd07634 (HS-SEC-016, OBS-1)
> review维度: 逐项闭合验证 / 回归确认 / 残留旧名扫描 / 测试全绿
> 上轮结论: ⏳ CONDITIONAL PASS (70 / 100, B) — 6 个 🟡 (HS-SEC-011~016) + OBS-1/2
> 本轮结论: ✅ PASS (100 / 100, A)

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push 数量与列表现状 | `git log origin/main..HEAD --oneline` | ✅ 10 个（与 prompt 所述 11 略有出入，见下注） |
| 修复提交范围 | `git diff 0dcbab2^ 0dcbab2` | ✅ 8 文件 14 行：MANIFEST.in / spec.yaml / release 脚本 ×2 / bookmark / history / dashboard ×2 |
| 修复提交范围 | `git diff fd07634^ fd07634` | ✅ 2 文件 4 行：CHANGELOG.md / handoff 文档 |
| 全量测试 | `PYTHONPATH=src python3 -m pytest tests/ -q` | ✅ 343 passed in 1.34s（与 claim 一致） |
| CLI 输出实测 | `hs version` | ✅ `http-server.cli v1.1.0`（与 spec.yaml L282 一致） |
| CLI JSON 实测 | `hs version --json` | ✅ name=http-server.cli, version=1.1.0 |
| sdist 实测 | `uv build --sdist` + `tar -tzf dist/http_server_cli-1.1.0.tar.gz` | ✅ tarball 内含 `http-server.cli.spec.yaml`，无旧名 spec |
| 残留旧名扫描（已排除 .git/缓存/构建产物） | `git ls-files \| xargs grep -l http-server-cli` | ✅ 仅剩合理保留（见回归确认） |
| /Users 字面路径扫描 | `grep -rn /Users/ src/ scripts/ tests/ documents/handoff/` | ✅ 活跃文件 0 命中；tests 中 /Users/test 为假路径 fixtures，documents/ 为历史文档示例 |

注：prompt 表述「未 push 共 11 个 commit（7 改名批次 + 审计 + 修复 2 + 既有 1）」，git 实测 `origin/main..HEAD` 为 10 个（f6a6909 属改名批次内的 handoff 提交，非单独「既有 1」；fc2db29 已在 origin/main）。以 git 为准，push 时全量推送 10 个。

## 逐项闭合验证

| # | 上轮发现 | 修复提交 | 当前状态 | 结果 |
|:--|:---------|:---------|:---------|:-----|
| HS-SEC-011 | bookmark.py:31 docstring `~/.http-server-cli/bookmarks.json` | 0dcbab2 | `存储文件: ~/.http-server.cli/bookmarks.json` | ✅ 已闭合 |
| HS-SEC-012 | history.py:4 docstring `~/.http-server-cli/history.json` | 0dcbab2 | `持久化至 ~/.http-server.cli/history.json。` | ✅ 已闭合 |
| HS-SEC-013 | dashboard.html:183 / dashboard.en.html:188 GitHub URL 旧名 | 0dcbab2 | 两处 href → `https://github.com/imjaden/http-server.cli` | ✅ 已闭合 |
| HS-SEC-014 | MANIFEST.in:1 悬空 include（打包回归） | 0dcbab2 | `include http-server.cli.spec.yaml`；sdist 实测 tarball 含新 spec | ✅ 已闭合（实测） |
| HS-SEC-015 | spec.yaml 内容 drift | 0dcbab2 | name=http-server.cli / version=1.1.0 / L282 输出串 / L408+L419 日志路径 全部同步；release-local.sh / release-pypi.sh 显示串亦同步 | ✅ 已闭合 |
| HS-SEC-016 | handoff 旧名标题 + /Users 绝对路径 | fd07634 | 标题 → `# Handoff: http-server.cli-review`；两处 /Users/jadenli 路径 → `$HOME/CodeSpace/http-server.cli/...` | ✅ 已闭合 |
| OBS-1 | CHANGELOG 1.1.0 日期 2026-08-19 | fd07634 | `## 1.1.0 (2026-08-23)` | ✅ 已闭合 |
| OBS-2 | 治理脚本枚举缺 feat@ | 本轮不动 | 记录项，无评分影响，继续挂账 | ⏸ 挂账（按约定） |

## 回归确认

- pytest 343 全绿（修复后复跑，与上轮一致）
- CLI 输出 `http-server.cli v1.1.0` 与 spec 场景 L282 完全一致，无行为 drift
- 全局旧名扫描剩余命中全部落在合理保留类别：
  - **1A pip/PyPI 包名**：pyproject.toml:6 `name = "http-server-cli"`、README/README.zh/index.html/index.zh.html 的 `pip install http-server-cli` 与 PyPI 链接、release-local.sh / release-pypi.sh 的 `pip show/index/install http-server-cli`（PyPI 包名未改，属改名决策保留项）
  - **迁移逻辑**：utils.py:19-20,48 LEGACY_DATA_DIR + tests/test_utils.py:136 迁移用例描述（必须引用旧目录才能测迁移）
  - **历史文档**：documents/*-v*-YYYYMMDD.md（hs-cli-design / bookmark-feature-design / pypi-release-steps / github-ci-* 等，按版本归档，改会破坏文档历史准确性）、review-log.md 与上轮报告自身引用
  - **CHANGELOG 历史条目**：1.1.0 条目本就描述改名过程（旧名→新名），更早版本条目为历史事实
- /Users 字面路径扫描：src/ scripts/ 0 命中；tests 中 `/Users/test/...` 为测试假路径；documents/ 命中均为历史设计文档示例或上轮报告引用

## 安全事项

本轮复查未发现新增 🟡/🔴 问题。两个修复提交均为纯文本替换（docstring / URL / include / spec 字段 / 显示串 / 文档路径），无新增代码路径、无新依赖、无敏感信息。

## 评分

| 等级 | 上轮数量 | 本轮数量 |
|:----:|:--------:|:--------:|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 6 | 0（全部闭合） |
| 🟢 LOW | 2（OBS-1/2） | 0（OBS-1 闭合，OBS-2 挂账记录） |

得分: 100 / 100 → Rating: A

## 结论

✅ **PASS** — HS-SEC-011~016 六个 🟡 全部闭合（0dcbab2 + fd07634），OBS-1 日期同步闭合，OBS-2 按约定挂账（🟢 记录项，不影响评分）。343 测试全绿，CLI 输出与 spec 一致，sdist 打包实测含新 spec，全局旧名扫描仅剩合理保留。修复提交无新引入问题。按规则 **push** origin main（10 个 commit 全量推送）。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | OBS-2 治理脚本默认枚举补 feat@（documents 治理文档 §5 枚举同步） | 记录项，后续轮次处理 |

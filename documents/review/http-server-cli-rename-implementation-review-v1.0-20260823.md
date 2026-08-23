# http-server.cli 改名批次 — commit audit review报告 v1.0

> 日期: 2026-08-23
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 待 push commit: 040c08f, 3b58879, a696253, b0e7bab, ec4b31a, 4ba0c57, f6a6909 (共 7 个)
> review维度: 迁移逻辑正确性 / commit规范 / 命名规范 / 残留旧名扫描 / 测试全绿
> 结论: ⏳ CONDITIONAL PASS (70 / 100, B)

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push 数量与列表现状 | `git log origin/main..HEAD --oneline` | ✅ 7 个，与 prompt 一致（ahead 7） |
| bookmark/--json feature commit 已 push | `git log origin/main --oneline` | ✅ 89ed981 / da5cfcb 已在 origin/main |
| 迁移逻辑代码审查 | `read_file src/http_server_cli/utils.py:47-74` | ✅ M2A move + M4A copytree 兜底 + 失败警告不中断 |
| 迁移真实行为（非 mock） | execute_code 实建旧目录 → ensure_storage | ✅ move 后旧目录移除，config/registry/logs 全部迁移，二次运行幂等 |
| 迁移单测 | `pytest tests/` | ✅ 5 个迁移用例通过（migrate/skip/no-legacy/copy-fallback/full-failure） |
| 全量测试 | `PYTHONPATH=src pytest tests/ -q` | ✅ 343 passed in 1.32s（与 claim 一致） |
| 版本串一致性 | `grep __version__; pyproject.toml dynamic; test_cli.py` | ✅ 1.1.0 三处一致（__init__ / dynamic attr / 测试断言） |
| version JSON name 字段 | 实跑 `hs version --json` | ✅ name=http-server.cli, version=1.1.0 |
| commit 格式扫描 | `scan-commits.py . origin/main..HEAD` | ⚠️ 7/7 均为 `type@scope: subject`；feat@ 因扫描脚本默认枚举缺 feat 而标记（见 OBS-2） |
| /Users 字面路径扫描 | `git diff origin/main..HEAD \| grep /Users` | ❌ 2 处，位于 f6a6909 handoff 文档 |
| 残留旧名扫描（已排除 .git/缓存/构建产物） | `git ls-files \| xargs grep -l http-server-cli` | ❌ 6 处活跃文件残留（见 SEC-011~016） |
| 敏感信息扫描 | `git diff origin/main..HEAD \| grep -iE 'api_key|secret|token|...'` | ✅ 0 命中 |
| hm 注册表同步 | `grep hermes-projects.yaml` | ✅ title=http-server.cli, path=~/CodeSpace/http-server.cli |

## 迁移逻辑评估（合理性/严格性）

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| M-1 | M2A move：`os.rename(LEGACY, DATA)` 原子移动整目录 | ✅ utils.py:62 |
| M-2 | move 后旧目录移除 | ✅ 实测 `old dir REMOVED after move: True`（tests/test_utils.py:157 亦断言） |
| M-3 | 新目录已存在 → 不迁移（新装/已迁移幂等） | ✅ utils.py:57-59 + test_skips_when_new_dir_exists |
| M-4 | M4A 失败回退：move 失败 → copytree 兜底，旧目录保留 | ✅ utils.py:64-70 + test_copy_fallback_on_move_failure |
| M-5 | 双失败 → 警告不中断，旧数据安全保留 | ✅ utils.py:71-74 + test_continues_on_full_failure |
| M-6 | 迁移触发点：ensure_storage() 在 cli.py:1173 主入口调用 | ✅ |

结论：迁移逻辑正确，5 单测 + 真实环境探测双重验证。函数级无缺陷。
(注：copytree 中途失败会留下部分新目录，下次运行因“新目录已存在”跳过迁移；旧目录仍保留可人工恢复。设计 M4A 决策“失败警告不中断”下可接受，记 OBS。)

## commit规范检查

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| C-1 | 7/7 subject 均为 `type@scope: subject` | ✅ docs@rename / test@rename / feat@rename / chore@package / chore@project ×2 / docs@handoff |
| C-2 | 分组按属性拆分（代码改名 / 包配置 / 项目配置 / 文档） | ✅ rename 按 docs/test/feat 与 chore 拆分，原子清晰 |
| C-3 | 无 /Users 字面路径 | ❌ f6a6909 生成的手写交接文档含 `/Users/jadenli/CodeSpace/http-server-cli/...`（见 SEC-016） |

## 命名规范检查

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| N-1 | spec 文件名 http-server-cli.spec.yaml → http-server.cli.spec.yaml | ✅ b0e7bab rename（点号是官方项目名，属改名决策本身） |
| N-2 | 数据目录 ~/.http-server.cli/ | ✅ utils.py:21 + 显示串 |
| N-3 | session title http-server.cli-ops/dev/review | ✅ .hermes-project.yaml:8-14 |
| N-4 | 残留旧名（排除 1A pip/PyPI 包名、5B 历史文档） | ❌ 6 处（见安全事项） |

## 安全事项

🟡 SEC-011 — bookmark.py:31 模块 docstring 残留旧数据目录

`存储文件: ~/.http-server-cli/bookmarks.json` — 实际存储已迁至 `~/.http-server.cli/bookmarks.json`（BOOKMARKS_PATH 由 DATA_DIR 派生）。活跃源码文档与实现不一致。
修复建议：docstring 改为 `~/.http-server.cli/bookmarks.json`。

🟡 SEC-012 — history.py:4 模块 docstring 残留旧数据目录

`持久化至 ~/.http-server-cli/history.json。` — 同 SEC-011。
修复建议：改为 `~/.http-server.cli/history.json`。

🟡 SEC-013 — dashboard 模板残留旧 GitHub 仓库 URL

`src/http_server_cli/dashboard.html:183` 与 `dashboard.en.html:188` 的 github-icon 链接仍为 `https://github.com/imjaden/http-server-cli`。同名 commit 040c08f 只更新了 index.html/index.zh.html，dashboard 两模板漏改。GitHub 会 301 重定向旧地址，但对外显示与改名目标不符。
修复建议：两处 href 改为 `https://github.com/imjaden/http-server.cli`。

🟡 SEC-014 — MANIFEST.in:1 悬空 include（打包回归）

`include http-server-cli.spec.yaml` — b0e7bab 将 spec 文件改名为 http-server.cli.spec.yaml，但 MANIFEST.in 未同步，include 匹配不到任何文件。1.0.8 的 sdist（egg-info/SOURCES.txt）曾包含该 spec；下次构建的 sdist 将静默丢失根目录 spec 文件（package-data `*.spec.yaml` 只覆盖包内目录，不含仓库根）。
修复建议：改为 `include http-server.cli.spec.yaml`。

🟡 SEC-015 — http-server.cli.spec.yaml 内容未随改名同步

- L1 `name: http-server-cli`（应 http-server.cli 或明确声明为 PyPI 包名）
- L2 `version: 1.0.8`（包已 bump 1.1.0；同文件 L282 场景却写 v1.1.0，自相矛盾）
- L282 `then: 输出 http-server-cli v1.1.0` — 实际 CLI 输出 `http-server.cli v1.1.0`
- L408/L419 `~/.http-server-cli/logs/8080.log` — 实际日志目录 `~/.http-server.cli/logs/`

行为规格与实现 drift：任何按 spec 校验输出的消费者会得到错误预期。
修复建议：name 字段与 version 字段同步为 http-server.cli / 1.1.0；L282 输出串改 `http-server.cli v1.1.0`；L408/L419 日志路径改 `~/.http-server.cli/logs/`。

🟡 SEC-016 — handoff 交接文档含 /Users 字面路径 + 旧名标题

`documents/handoff/handoff-http-server.cli-review.md`（f6a6909 新建）：
- L11 `# Handoff: http-server-cli-review` — 标题用旧名，与文件名（新名）不一致
- L21 `/Users/jadenli/CodeSpace/http-server-cli/documents/url-flag-design-v1-20250715.md` — 机器特定绝对路径且目录名是改名前的旧值，违反 commit规范“无 /Users 字面路径”

修复建议：标题改 `http-server.cli-review`；目标路径去掉绝对路径前缀（改用相对路径或 `~/CodeSpace/...` 并写新目录名）。

## 评分

| 等级 | 数量 | 扣分 |
|:----:|:----:|:----:|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 6 | -30 |
| 🟢 LOW | 2 | 0（仅记录） |

得分: 70 / 100 → Rating: B

## 结论

⏳ **CONDITIONAL PASS** — 迁移逻辑正确（真实环境验证 + 5 单测），343 测试全绿，commit 格式与分组合规，命名主体正确。但“改名后无残留旧名”验收项未通过：6 处活跃文件/新文档残留旧名，其中 MANIFEST.in 悬空 include 属打包回归、spec 内容 drift 影响行为校验、handoff 含 /Users 字面路径。按规则**不 push**，回 ops 修正（每项均给出 file:line）。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | SEC-011 bookmark.py:31 docstring 数据目录改新名 | 命名 🟡 |
| □ | SEC-012 history.py:4 docstring 数据目录改新名 | 命名 🟡 |
| □ | SEC-013 dashboard.html:183 / dashboard.en.html:188 GitHub URL 改 http-server.cli | 命名 🟡 |
| □ | SEC-014 MANIFEST.in:1 include 改 http-server.cli.spec.yaml | 打包 🟡 |
| □ | SEC-015 spec.yaml name/version/输出串/日志路径同步 1.1.0 | 规格 🟡 |
| □ | SEC-016 handoff 标题改新名、去掉 /Users 绝对路径 | commit规范 🟡 |
| □ | OBS-1 CHANGELOG 1.1.0 日期 2026-08-19 与提交日期 08-23 不符 | 记录 |
| □ | OBS-2 扫描脚本默认枚举缺 feat@（项目惯例使用，非本次缺陷；治理文档 §5 枚举待补 feat） | 记录 |

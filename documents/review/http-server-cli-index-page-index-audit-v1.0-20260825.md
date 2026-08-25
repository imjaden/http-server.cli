# CL-SEC19 index 落地页 page-index 对齐批 — commit audit报告 v1.0

> 日期: 2026-08-25
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 待 push commit: 92250f4, 95cf6f7, a039321, 5f7028e, 84f53d9(共 5 个)
> review维度: 提交审计(审计规范 §6 + commit规范 §5 + 命名规范 §1)
> 闭环: CL-SEC19 — index 落地页 page-index 对齐批(T1 两列首屏 / T2 场景网格 3 列 / T3 对齐 html-gen page-index 结构 / T4 手工微调定案 + data-copy 修正)

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push commit 恰为 5 个 | `git log origin/main..HEAD --oneline` | ✅ 92250f4 / 95cf6f7 / a039321 / 5f7028e / 84f53d9 |
| src/ 无源码变更 | `git diff origin/main..HEAD --stat` | ✅ 0 文件;变更面 = index.html + index.zh.html + tests/test_index_sync.py + features.md + documents/review/建议文档 |
| 双页组数 = 5 | grep class="group-title" | ✅ EN 5 / ZH 5(EN: Start/Bookmark/View/Kill/Manage;ZH: 启动/书签/查看/关闭/管理) |
| 场景 cmd-row = 14 | grep class="cmd-row" | ✅ EN 14 / ZH 14(2+3+4+3+2 分布一致) |
| 首屏 code-block = 4 | grep '<div class="code-block">' | ✅ EN 4 / ZH 4(hs -o / hs --open --index index.html / hs list / hs kill 8081) |
| 对比表 <tr> = 6 | grep '<tr>' | ✅ EN 6 / ZH 6(1 表头 + 5 工具) |
| title 全称 | grep '<title>' | ✅ EN/ZH 均 `<title>HTTP Server — ...`(hs 缩写不残留 title) |
| hero 动态高度 | grep 'window.innerHeight' | ✅ 双页 `window.innerHeight - 55`(84f53d9 由 -110 修正) |
| data-copy 与 .cmd 一致 | 脚本提取 data-copy × 19 逐一比对 | ✅ 19/19 不含 $ 提示符;4 条 code-block data-copy 与显示命令逐字一致;14 条场景 cmd-row 同验 |
| 结构特征(脚本抽验 25 项) | cache/review-prep/cl-sec19-audit-check.py | ✅ 双页全在(hero-title/hero-tagline/hero-blocks/hero-block/block-title/code-block/scroll-bounce/templates-title/templates-sub/template-grid/back-top-link/site-footer/id="top"/flex 1 1 340px/max-width 1024px/repeat(3,1fr)/1200px/1500px/1100px 断点/border-radius 10px/npm-note/favicon/updateHeroHeight/jaden.tech) |
| 无旧结构残留 | 8 模式 grep(quick-start/quick-compare/qs-col/cmp-col/scenarios-grid/jaden.local/旧链接连字符/title hs) | ✅ 全部 0 hits(双页) |
| test_index_sync.py 14 用例与页面一致 | `pytest tests/test_index_sync.py -q` | ✅ 14/14 passed(含 STRUCTURE_FEATURES 37 项、组数/行数/复制按钮计数、title、height-55、page-index 对齐、渐变、断点、aria-pressed、无旧链接) |
| 全量测试绿 | `pytest tests/ -q`(.venv) | ✅ **357 passed in 1.44s** |
| features.md 同步 | git diff features.md | ✅ 352→355→356→357 三段随测试用例数同步(最终 357,与实测一致) |
| favicon 可访问 | curl -L 逐个 | ✅ 3/3 200(GitHub/PyPI/站点图标,设计文档 3A 要求) |
| 无敏感信息 | diff grep key/secret/token/private | ✅ 0 hits |
| 工作区 .hermes-project.yaml 未混入 | git diff origin/main..HEAD --name-only | ✅ 不在 5 commit 内(并发会话 WIP,未提交) |
| commit 格式合规 | scan-commits.py . origin/main..HEAD --type feat,docs | ✅ 5/5 ok,0 violations,exit 0 |
| 命名规范 | 变更文件清单 | ✅ 新增 1 文件 kebab-case;现有文件未改名(见 §1 评估) |

## 审计规范评估(§6)

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| A1 | index 双页对称 — title/hero-title/hero-tagline/badges/install-box/hero-blocks(block-title)/code-block 命令 4 条/对比表 6 行/场景区(Start+Bookmark、View、Kill+Manage)/templates-title/sub/scroll-hint/footer/npm 注记 EN/ZH 全部对应 | ✅ 双页 651/651 行结构对齐,命令串逐字一致,文案成对翻译(Quick start↔快速开始、Comparison↔功能对比、Scenarios↔场景详解、Start/Bookmark/View/Kill/Manage↔启动/书签/查看/关闭/管理) |
| A2 | data-copy 与 .cmd 显示命令一致(84f53d9 修正项) | ✅ 4 条 code-block + 14 条 cmd-row 共 19 处 data-copy 全部与显示命令一致,不含 $ prompt(脚本提取比对) |
| A3 | page-index 结构要素齐全 | ✅ hero-title/hero-tagline/hero-blocks/hero-block/block-title/code-block/scroll-bounce/templates-title/templates-sub/template-grid/back-top-link/site-footer/id="top" 双页全在;scroll-hint href="#templates" 指向第二屏 |
| A4 | 无旧结构残留 | ✅ 8/8 模式 0 hits;旧链接连字符形态 `github.com/imjaden/http-server-cli` 0 hits,现链接均为点形态 http-server.cli |
| A5 | test_index_sync.py 断言与实际页面一致 | ✅ 14 用例逐项与页面实测吻合:组数 5 / cmd-row 14 / code-block 4 / <tr> 6 / title "HTTP Server" / innerHeight - 55 / 结构特征 37 项全在 |
| A6 | 357 tests 全绿 | ✅ 实测 357 passed(.venv) |
| A7 | 改动未触碰源码逻辑 | ✅ src/ 0 变更;5f7028e 仅 documents/review/ 建议文档 |

## commit规范评估(§5)

| # | 检查项 | 结果 |
|:--|:-------|:-----|
| C1 | subject 格式 `type@scope: subject` | ✅ feat@index ×4 + docs@review ×1 — 5/5,scope 均非空(scan-commits.py 0 violations) |
| C2 | 分组按属性 | ✅ 4×feat@index 为 index 双页+同步测试演进;1×docs@review 为纯建议文档。features.md 测试计数 3 处随对应 feat commit 同步(见 SEC-019-1 🟢 记录) |
| C3 | 无 /Users 字面路径 | ✅ 代码/配置 0 hits;2 处 hits 均在 5f7028e 建议文档(参考源说明,与既有 review/design 文档惯例一致,见 SEC-019-2 🟢) |
| C4 | .hermes-project.yaml 未混入 | ✅ 不在 5 commit 内,工作区 M 状态保持未提交 |
| C5 | 无敏感信息 | ✅ diff 无密钥/凭证/token |

附注:5 commit body 均为空 — 与本项目既有历史惯例一致(近 10 个 commit 均无 body),小提交 subject 自含信息,不构成违规。

## 命名规范评估(§1)

- ✅ 新增文件仅 `documents/review/html-gen-optimize-suggestions-20260825.md` — 全小写 kebab-case、日期 8 位、无点/无下划线;作为跨项目回哺建议的工作文档,§1 原则豁免版本段(见 SEC-019-3 🟢)
- ✅ 既有文件(index.html / index.zh.html / tests/test_index_sync.py / features.md)未改名
- ✅ 无新设计文档

## 安全事项

🟢 SEC-019-1 — features.md 测试计数内嵌于 feat@index commit(352→355→356→357,3 处各随对应 commit 的测试用例数变化同步),与前批 CL-SEC17 独立 docs commit 惯例不同;但每 commit 保持"文档-代码原子一致",无漂移窗口,记录不扣分。

🟢 SEC-019-2 — 5f7028e 建议文档含 2 处 `/Users/jadenli/CodeSpace/...` 参考源路径(参考源/参考实现说明);既有已 push 的 review/design 文档均含同类路径(如本报告头部、CL-SEC17 报告),属文档惯例,非代码/配置文件,记录不扣分。

🟢 SEC-019-3 — 新文档 `html-gen-optimize-suggestions-20260825.md` 缺 `v{major}.{minor}` 版本段;§1 原则明确"工作文件(按场景命名的持续更新/一次性建议文档)不套用版本格式",且该文档目标项目为 html-gen.cli(跨项目回哺),命名语义清晰,记录不扣分。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 HIGH × 0 | −0 |
| 🟡 MEDIUM × 0 | −0 |
| 🟢 LOW × 3(SEC-019-1/2/3) | −0 |
| **得分** | **100 / 100 → Rating A** |

## 结论

**✅ PASS(100/100, A)** — CL-SEC19 四项任务全部核验通过:两列首屏 + 场景网格结构完备、page-index 结构要素 25+ 项双页齐全、data-copy 与显示命令 19/19 一致(84f53d9 修正闭环)、无旧结构残留 8/8、防漂移测试 14 用例与页面实测吻合、357 全绿、src/ 零变更、favicon 3/3 200。commit 格式 5/5 合规、命名规范合规。**授权 push 已执行**。

**Push 结果**: `git push origin main` → `fa853e3..84f53d9 main -> main`;origin/main 新 tip = `84f53d9`(feat@index: adopt manual tweaks ...),ahead 0。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| — | 无未决项 | — |

工作区 `.hermes-project.yaml` 修改为并发会话 WIP(承 OBS-1,未提交,不随本批 push),已排除于审计范围。

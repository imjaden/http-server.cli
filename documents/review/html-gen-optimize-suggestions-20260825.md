# html-gen 落地页优化建议（回哺自 http-server.cli 四轮迭代）

日期: 2026-08-25
来源: http-server.cli index.html 4 轮迭代（探讨→决策→实施，全量测试通过）
参考源: /Users/jadenli/CodeSpace/html-gen.cli/index.html（page-index 规范，已作为 http-server 对齐基准）

## 背景

http-server.cli 落地页按 html-gen page-index 规范完成重构（hero-title 渐变 / hero-blocks 卡片 /
code-block 命令行 / templates 第二屏网格 / scroll-bounce / back-top / site-footer）。
重构过程中 http-server 保留并新增了若干 html-gen 参考页没有的能力，以下为可供 html-gen 参考完善的建议。

## 建议清单

### A. 快速开始块 code-block 行内复制按钮（建议采纳，价值高）
- 现状: html-gen 🚀 快速开始块 4 条 code-block 无复制按钮（仅 ⚡ 安装块 block-title 与第二屏 tpl cli-box 有）
- 建议: 每条 code-block 右侧加行内 copy-btn（data-copy + copyText 事件委托，✅ 反馈 1.5s）
- 理由: 快速开始是用户最常复制的命令区，首屏直达复制价值最高
- 参考实现: http-server index.html `.code-block` flex 布局 + `.code-block .copy-btn`（border-left 分隔）
- 测试影响: test_index_landing copy 按钮计数断言需 +4（5→9 或按 code-block 数断言）

### B. 竞品对比卡（Comparison，建议采纳）
- 现状: html-gen 无竞品对比
- 建议: hero-blocks 后加一张 Comparison 卡（vs 手写 HTML / pandoc / mdbook 等，行: 起始成本/模板体系/主题/单文件/零依赖/上手速度）
- 理由: 对比表是"为什么选我"最直接的说服工具；http-server 实证效果好（首屏右侧卡）
- 参考实现: http-server hero-block 内 table-wrap（11px + td:first-child nowrap + overflow-x auto）
- 测试影响: 新增结构特征断言（对比表行数/卡片存在）

### C. badges 特性徽章行（可选）
- 现状: html-gen hero = title + tagline + blocks，无特性徽章
- 建议: hero-tagline 下加一行特性徽章（如 ⚡ 零依赖 · 🌙 深色主题 · 🇨🇳 中文优先 · 📦 单文件输出）
- 理由: 首屏信息密度提升，用户 3 秒内抓到核心卖点；http-server badges 实证
- 注意: html-gen tagline 已较长，badges 可简短（3-4 项）
- 测试影响: 新增 badges 特征断言

### D. footer favicon 图标化（可选）
- 现状: html-gen footer 为文本链接（GitHub · Gitee · MIT）
- 建议: 平台链接改用 favicon 图标（github.com/favicon.ico、gitee.com/favicon.ico）+ 文本
- 理由: 视觉统一、识别更快；http-server 三图标 footer 实证
- 注意: 图标逐个 curl 验证 200（PyPI 新 UI favicon 带 hash 易 404）
- 测试影响: footer 链接断言改为含 img 或保留文本断言均可

### E. 品牌圆标 + 渐变标题（可选）
- 现状: html-gen hero-title 纯文本渐变（无图标）
- 建议: 若后续有品牌图标（如 favicon 同款 svg），可前置在 hero-title 内（flex + gap）
- 理由: http-server 保留 hs 圆标后标题辨识度更高；html-gen 品牌为文字本身，此项优先级低

## 不适用/无需建议

- 语言切换 EN/ZH（html-gen 中文优先策略，工作量大收益低，暂不建议）
- npm 同名注记（html-gen 无同名冲突）
- scroll-bounce / back-top / 动态两屏 / 主题切换（html-gen 已有）

## 决策项（html-gen session 逐项回复编号+字母）

1. A 快速开始行内复制 — 1A 采纳（推荐）/ 1B 跳过
2. B 对比卡 — 2A 采纳（推荐）/ 2B 跳过
3. C badges — 3A 采纳 / 3B 跳过（推荐先跳过，tagline 已承载）
4. D footer 图标 — 4A 采纳 / 4B 跳过（推荐 4A）
5. E 品牌圆标 — 5A 采纳 / 5B 跳过（推荐 5B，优先级低）

## 交接说明

- 本文件只提供建议，不修改 html-gen 项目文件（跨项目约束）
- 采纳项按 html-gen 既有流程（探讨→设计→review→dev→ops 核查）推进
- 参考实现均可查看 /Users/jadenli/CodeSpace/http-server.cli/index.html（已 commit a039321，全量 357 tests PASS）

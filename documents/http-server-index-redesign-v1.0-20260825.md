# http-server index 两屏重构 + 展示名调整 + PyPI 描述修复 设计 v1.0

日期: 2026-08-25
作者: ops
状态: 已确认（决策 1A-8A + 补充 + 1B/2A/3A 全收敛）

## 背景

http-server.cli 的 GitHub Pages 落地页（index.html / index.zh.html 双源）为单页长版式：
hero + intro + 5 场景组 + 对比表。用户要求：

1. 展示名统一为 **http-server**（缩写 hs），PyPI 包名 http-server-cli 不变
2. 使用 html-gen.cli 的 pages-index 规范重构为**两屏模式**：首屏=介绍+简洁部署与使用指令，第二屏=按场景详细介绍
3. 修复 PyPI 描述缺失问题（"The author of this package has not provided a project description"）
4. PyPI 描述与 GitHub/落地页互相体现链接；平台链接统一用 favicon 图标

## 决策记录

| 项 | 决策 | 说明 |
|----|------|------|
| 1. 改名范围 | 1A | 只改展示名，内部标识全保留 |
| 2. 主品牌文案 | 2A | http-server |
| 3. npm 混淆注记 | 3A | README + index 双处"与 npm http-server 无关" |
| 4. 两屏结构 | 4A | 首屏=hero+install+quick start；第二屏=现有 5 场景组+对比表 |
| 5. 复制按钮 | 5A | 首屏 install + quick start 每条、第二屏每条命令行 |
| 6. 主题机制 | 6A | 保留 [data-theme=light]+hs-theme，只补 github-corner 浅色 |
| 7. 版本策略 | 7A | 并入 1.1.0 一次发布 |
| 8. 测试策略 | 8A | 重构同步更新 test_index_sync.py 特征串 + 定向跑 |
| 补充 1 | — | PyPI 规范链接 https://pypi.org/project/http-server-cli |
| 补充 2 | — | 修复 PyPI 描述缺失（根因：v1.0.8 readme 指向不存在的 README.en.md） |
| 补充 3 | — | PyPI 描述体现 GitHub 链接；README + index 体现 PyPI 链接 |
| 补充 3A | 1B/2A/3A | footer 暂不放 gitee（gitee 无镜像 404）；个人站点=http-server.cli.jaden.tech；图标用官方 favicon（实施时验证 200） |

## 一、展示名调整（仅展示层）

内部标识**保持不变**：repo 名 http-server.cli / Pages 域名 http-server.cli.jaden.tech /
数据目录 ~/.http-server.cli / spec 文件 http-server.cli.spec.yaml / PyPI 包名 http-server-cli /
模块名 http_server_cli。

展示名改动点：

| 文件 | 位置 | 现值 | 新值 |
|------|------|------|------|
| src/http_server_cli/__init__.py | docstring 首行 | http-server.cli — 本地 HTTP 服务管理器 | http-server — 本地 HTTP 服务管理器 |
| src/http_server_cli/cli.py | _HELP L19 | http-server.cli v{version} | http-server v{version} |
| src/http_server_cli/cli.py | L532 name 字段 | 'http-server.cli' | 'http-server' |
| src/http_server_cli/cli.py | L538 version print | http-server.cli v{__version__} | http-server v{__version__} |
| src/http_server_cli/config.py | L76 | 📋 http-server.cli configuration | 📋 http-server configuration |
| README.md / README.zh.md | h1 | http-server.cli | http-server |
| features.md | 标题 | # http-server.cli — Features | # http-server — Features |
| index.html / index.zh.html | hero logo span | http-server.cli | http-server |

数据目录字符串（~/.http-server.cli）出现在 cli.py L85、__init__.py L13-16、bookmark.py L31、
config.py、history.py、utils.py L19-20 —— **全部不动**。

## 二、index 两屏重构（pages-index 规范适配）

### 骨架

```
<body>
  toolbar（lang 切换 + theme-btn，保留现有）
  github-corner（补浅色覆盖）
  <section class="hero">            ← 首屏 = 动态两屏高度
    logo（hs 图标 + http-server）
    tagline + badges
    install-box（pip install http-server-cli + copy）
    quick start（4-6 条核心命令，每条可复制）
    scroll-hint（fixed bottom + scrollY>8 淡出）
  </section>
  <section class="scenarios">       ← 第二屏 = 5 场景组（Start/View/Kill/Bookmark/Manage）
    每组 group-title + 命令行（每条带 copy-btn）
  </section>
  <section class="compare">         对比表（保留现有 6 行）
  <footer>                          GitHub/PyPI/站点 favicon 图标 + MIT
</body>
```

### 关键实现点

1. **动态两屏 JS**：`hero.style.minHeight = (window.innerHeight - 110) + 'px'` + resize 监听；
   CSS 保留 `min-height: 80vh` 兜底
2. **scroll-hint**：`position: fixed; bottom: 24px` + scrollY>8 加 .hide 淡出、回顶恢复
3. **复制按钮扩展**：从仅 install-box 扩展到 quick start 每条命令 + 第二屏每组命令行。
   采用现有 copyInstall 模式（clipboard API + execCommand fallback），data-copy 语义：
   quick start 与场景命令行复制的是命令本身（不含 $ 提示符）
4. **主题机制保留**：[data-theme=light] + hs-theme localStorage key 不动；
   补 github-corner 浅色覆盖：
   - `[data-theme="light"]` 块补 `--gh-corner-fill: rgba(0,0,0,0.75)` / `--gh-octocat: #ffffff`
   - 补 `.github-corner:hover` 保护（浅色下 octocat 保持白）
5. **intro 段**：现有 intro 两段文字并入 hero 区（首屏介绍），避免独立区块割裂
6. **quick start 4 条**：`hs -o` / `hs list` / `hs kill 8080` / `hs dashboard -o`（含说明注释）
7. **npm 注记**：hero tagline 下或 footer 加 "独立工具，与 npm http-server 无关"
   （README 同步）

### 双源同步

- EN（index.html）先行重构，ZH（index.zh.html）同步同结构（文案翻译）
- test_index_sync.py STRUCTURE_FEATURES 更新：加 hero/quick-start/scroll-hint 特征，
  保留 toolbar/themeBtn/github-corner/install-box/copy-btn/group-title/compare/footer 等；
  场景组数断言维持 5；对比表行数维持 6

## 三、PyPI 描述修复

- **根因**：v1.0.8 发布时 pyproject.toml `readme = "README.en.md"`（文件不存在）
  → setuptools 生成 metadata 的 long_description 为空 → PyPI 显示
  "The author of this package has not provided a project description"
- **现状**：pyproject.toml 已修正 `readme = "README.md"`（CHANGELOG 1.1.0 记录）
- **验证**：发布前 `python3 -m build` 后检查 long_description 非空（twine check 或读取 metadata）
- **Homepage 已修正**：v1.0.8 是 github.com/imjaden/http-server-cli（旧名），
  现为 github.com/imjaden/http-server.cli（正确）

## 四、链接与图标

| 位置 | 内容 |
|------|------|
| README.md/zh 徽章区（h1 下） | github + pypi favicon 图标链接 |
| README.md/zh 正文 | 安装节加 PyPI 链接；显式 GitHub 仓库链接 |
| index.html/zh footer | github + pypi + 站点（http-server.cli.jaden.tech）3 个 favicon 图标 + MIT 文本；gitee 暂不放（无镜像） |
| index.html/zh hero | npm 注记 |
| PyPI 描述（=README.md） | 自动包含 GitHub 链接 |

favicon 来源（实施时逐个 curl 验证 200，坏图回退）：
- GitHub: https://github.com/favicon.ico
- PyPI: https://pypi.org/static/images/favicon.ico
- 站点: https://raw.githubusercontent.com/imjaden/http-server.cli/main/src/http_server_cli/hs-icon.svg
  （即现有 index.html 的 icon 同源，本地可用）

## 五、版本与发布

- 版本号保持 **1.1.0**（代码与 CHANGELOG 已存在，从未发布到 PyPI）
- CHANGELOG 1.1.0 条目补记：展示名调整 + index 两屏重构 + PyPI 描述修复说明
- 发布：build → twine check → release 脚本上传 PyPI → tag v1.1.0 → push → Pages 自动部署验证

## 六、测试影响

- tests/test_index_sync.py：特征串更新（见二.双源同步）
- tests/ 中 33 处 http-server.cli 命中：绝大多数是 ~/.http-server.cli 数据目录路径断言（不动）；
  需定向 grep 出断言显示名（http-server.cli v / name / configuration）的用例并更新
- 全量 pytest（350 tests, 12 modules）作为发布前回归

## 七、commit 分组

1. docs@redesign: 设计文档
2. chore@rename: 展示名替换（src + README + features + 测试断言）
3. feat@index: index 两屏重构（EN/ZH 双源 + test_index_sync 更新）
4. docs@readme: README 徽章区 + npm 注记 + 双向链接
5. release@v1.1.0: CHANGELOG 补记 + 发布

## 风险与边界

- index 重构是页面结构重写，EN/ZH 双源与防漂移测试是主要成本
- 展示名改动涉及 CLI 输出，属用户可见变更，测试断言必须同步
- gitee 链接本期不放（无镜像），后续建镜像再补
- 不修改其他 profile 数据；.hermes-project.yaml 的 M 状态为既有自动变更，不纳入 commit

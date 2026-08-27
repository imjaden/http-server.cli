# HTTP-SERVER-CL002 复核 — SEC-023-1 set_domain 字符集校验 — review报告 v1.1

> 日期: 2026-08-27
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 审计对象: 3 commits（03ca74b, 14e08cf, b33e2f1），基底 origin/main 09d9e3b（CL002 PASS 95/100）
> review维度: 提交审计（审计规范 §6 + commit规范 §5 + 命名规范 §1）+ 定向测试 + SEC-023-1 闭环
> 闭环: CL002 遗留 🟢 记录项 SEC-023-1 —— `hs web --domain` 注入 `Config().domain` 到 shell 命令仅双引号包裹，`set_domain` 无校验 → 补字符集校验（defense-in-depth）

## 数据验证（6 项审计项，逐条核验）

| # | 审计项 | 方法 | 结果 |
|:--|:-------|:-----|:-----|
| 1 | 校验实现 | config.py:12 `_DOMAIN_RE` + config.py:56-69 `set_domain` | ✅ `_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$')`；`set_domain` 先 `if not isinstance(value, str) or not _DOMAIN_RE.match(value): raise ValueError` 后 `self._data['domain'] = value; self._save()`——非法值先校验后赋值，不持久化 |
| 2 | CLI 捕获 | cli.py:146-159 `_handle_set` domain 分支 | ✅ `try: config.set_domain(value) except ValueError as e:` → json 信封 `json_output(False, 'set', error=str(e))` / 文本 `eprint(str(e), '❌')`，随后 `return`；不写入 config；port 分支（cli.py:123-145）未触碰 |
| 3 | --domain 注入不受影响 | cli.py:1715 注入点 + config.json 实测 | ✅ 注入逻辑 `cmd_line = f"{cmd_line} --domain \"{Config().domain}\""` 未改；`set_domain` 是 domain 唯一写入口（`_merge_file` 直读不校验）；现有 config.json `domain: jaden.local` 合法 |
| 4 | 测试 | .venv pytest 定向 + 全量 | ✅ `TestSetDomainValidation` 21 例（6 合法 + 14 非法 + 1 不持久化）+ `TestSetDomainCli` 3 例 = **24 passed**；全量 **483 passed in 1.35s**（.venv Python 3.11.15）零回归，features.md 459→483 同步 |
| 5 | 范围控制 | `git diff --name-only origin/main..HEAD` | ✅ 仅 6 文件（config.py / cli.py / tests×2 / CHANGELOG.md / features.md）；bookmark/web 执行逻辑未动；`__version__ = 1.3.0` 未 bump（spec.yaml 亦 1.3.0） |
| 6 | 文档同步 | CHANGELOG.md + features.md | ✅ CHANGELOG 1.3.0 增「SEC-023-1（CL002 复核）」条目 + 测试数 442→483；features.md 测试节 459→483 |

## 维度评估

**commit 规范 §5** — 3/3 合规：
- 03ca74b `feat@config:` / 14e08cf `tests@config:` / b33e2f1 `docs@config:` — type@scope 格式正确，scope 非空
- 分组按属性无混批：校验 + CLI 捕获 → feat@config；24 例测试 → tests@config；测试数 + CHANGELOG → docs@config
- 3 条 type 均在项目历史类型集（feat/tests/docs）

**命名规范 §1** — 合规：
- 无新增文件；报告文件名 kebab-case；diff 无 `/Users` 字面路径（0 hits）

## 安全事项

| # | 严重度 | 说明 | 状态 |
|:--|:------|:-----|:-----|
| SEC-023-1 | 🟢（记录，已闭环） | 字符集 `[a-zA-Z0-9][a-zA-Z0-9.-]*` 拒绝空格/引号/`$`/反引号/`;`/`&`/`|`/`(`/换行/重定向等全部 shell 元字符。注入点在双引号内（cli.py:1715），双引号内可破出的 `"`/`$`/反引号/`\` 全部落在拒绝集，`;`/`&&`/`|`/空格/换行亦被拒——defense-in-depth 到位 | ✅ Closed (03ca74b/14e08cf/b33e2f1) |
| SEC-023-2 | 🟡（已闭环） | 原 services.json 第三条 `dk` 测试残留，经 ops 清理后实测 `~/.http-server.cli/services.json` 现仅 daily.checker + jaden.tech 两条 intact，第三条已移除 | ✅ Closed (ops 清理，本次复核实测确认) |

> **残留说明（非新发现）**：`Config._merge_file` 直读 config.json 不做校验（用户可手改 config.json 绕过 `set_domain` 校验），属设计明示的「信任用户自行为」边界（config.py:61 docstring 已注明），攻击面 = 用户自有 config，无外部输入流入，不构成新缺陷。`set_domain` 字符集仅接受 ASCII 字母数字 + `-`/`.`（连字符/点非 shell 元字符，注入安全），对非 ASCII/IDN 域名偏保守但非安全回归。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 | −0 |
| 🟡 | −0 |
| 🟢 | −0（SEC-023-1 为既有记录项闭环，非新发现） |
| **得分** | **100 / 100 → Rating A** |

## 结论

**✅ PASS（100/100, A）** — 6 项审计全过，零新发现。SEC-023-1 字符集校验完整落地：`set_domain` 先校验后持久化（`_DOMAIN_RE` 拒绝全部 shell 元字符，非法抛 ValueError 且不落盘），`hs set domain` CLI 捕获 ValueError 走 json 信封 / 文本错误（不写 config），`--domain` 注入逻辑未动（现有 config.json `jaden.local` 合法，注入面收窄至经 CLI 写入必合法）。24 例新测试（21 config + 3 CLI）全绿，全量 483 零回归，范围控制到位（仅 6 文件，版本 1.3.0 未 bump）。附带确认 SEC-023-2（注册表 `dk` 残留）已由 ops 清理。**commit audit@review + push（origin/main 推进至 b33e2f1）**。

## 待确认清单

| □ | 项 | 类别 |
|:--|:---|:-----|
| — | 无待确认项（SEC-023-1 代码闭环 + SEC-023-2 ops 清理均已实测确认） | — |

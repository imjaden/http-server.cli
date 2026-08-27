# HTTP-SERVER-CL002 hs web --domain 入参 + hs-web skill 推广 + CL001 遗留 — review报告 v1.0

> 日期: 2026-08-27
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 审计对象: 3 commits（38e4ee0, 5e1e20a, 197c27a），基底 origin/main cf40dcb
> review维度: 提交审计（审计规范 §6 + commit规范 §5 + 命名规范 §1）+ 功能实测 + CL001 遗留闭环
> 闭环: HTTP-SERVER-CL002 — hs web --domain 入参 + hs-web skill 推广 + SEC-022-1/2 + OBS-3

## 数据验证（10 项审计项，逐条核验）

| # | 审计项 | 方法 | 结果 |
|:--|:-------|:-----|:-----|
| 1 | --domain 功能 | cli.py:1319/1551（add/update 注册）+ services.py:116-152（use_domain 字段）+ cli.py:1704-1708（执行注入）+ test_web domain 类 | ✅ add `--domain` store_true → use_domain=True；update `--domain`/`--no-domain`（no_domain 优先清除，cli.py:1610-1615）；执行 `use_domain=True` → `cmd_line = f"{cmd_line} --domain \"{Config().domain}\""`；json 输出 `cmd_effective`（cli.py:1722） |
| 2 | open/url 不受影响 | cli.py:1689-1707 执行路径 + test_domain_injected `mock_probe.assert_not_called()` | ✅ --domain 仅改 cmd 拼接（cli.py:1704-1707）；探测仍走 url（cli.py:1690 `if url and not parsed.no_probe`）；open 四态 url/cmd/both/none 逻辑未触碰 |
| 3 | SEC-022-1（CL001 遗留） | cli.py:1272 `_WEB_SUBCOMMANDS` + cli.py:1349 冲突判断 + test_add_subcommand_name_conflict / test_add_help_subcommand_name_conflict | ✅ `_WEB_SUBCOMMANDS = {'add','update','list','show','remove','help'}`；`_web_add` 冲突判断扩展为 `name in _COMMANDS or name in _WEB_SUBCOMMANDS` → `conflicts with built-in command` + 不写入；顶层命令冲突仍拦截 |
| 4 | SEC-022-2（CL001 遗留） | services.py:53-69 `_read_all` + test_json_not_dict_raises / test_json_string_raises / test_services_not_list_raises / test_legit_dict_ok | ✅ 三类损坏 → DataCorruptionError：非空 JSON 语法错（`if not raw and getsize>0`）/ 合法 JSON 非 dict（`[1,2,3]`/`"str"`）/ services 非 list（`{"services":{}}`）；空文件 `if not raw: return []` 仍 OK；legit dict `{"services":[]}` OK |
| 5 | OBS-3（CL001 遗留） | http-server.cli.spec.yaml:2 + :291 + 全文件 version grep | ✅ version 1.1.0→1.3.0（L2）；version 场景 `then: 输出 http-server v1.3.0`（L291，修正 `http-server.cli` 串为 `http-server`）；spec 全文件无其他过期 v1.x（仅 L291 一处版本串；`--version 标志` 场景 L295 `then: 输出版本号` 为泛化文案） |
| 6 | hs-web skill | skills/hs-web/SKILL.md + `hs prompt` 实测 + test_prompt EXPECTED_SKILLS + 镜像 | ✅ SKILL.md 存在且 frontmatter 合法（name + description）；`hs prompt` 列表 6 篇含 hs-web；`hs prompt hs-web --brief` 解析输出章节；test_prompt `EXPECTED_SKILLS = {...ai-interchange, hs-web}`（6 全等）；镜像 `~/.hermes/profiles/ops/skills/devops/hs-web/SKILL.md` 与源逐字节一致 |
| 7 | 文档同步 | README.md/zh + features.md + CHANGELOG.md + __version__ + hs version | ✅ README EN/ZH "Ships 6 skills" + Web 服务注册节补 `[--domain]`/`[--domain\|--no-domain]`；features.md Web 节 14 条（含 --domain/子命令名/形状校验/推广）+ AI 对接节 6 篇 + 测试数 459；CHANGELOG 1.3.0 扩充 CL002；版本四同步 `__version__=1.3.0` = spec.yaml 1.3.0 = `hs version` 实测 `http-server v1.3.0` |
| 8 | 测试 | .venv pytest + grep def test_ | ✅ test_web 81 例（64+17）；全量 **459 passed in 1.36s**（.venv Python 3.11.15）；grep `def test_` 求和 459 = features.md 442→459 同步 |
| 9 | 注册表状态 | 实测 services.json | ⚠️ daily.checker + jaden.tech 两条 intact ✓；demo-cl002 已清理 ✓；**但存在第三条 `dk` 测试残留**（见 SEC-023-2） |
| 10 | 范围控制 | git diff --name-only cf40dcb..HEAD | ✅ 仅 10 文件（cli.py/services.py/test_web.py/test_prompt.py/README×2/features.md/CHANGELOG.md/spec.yaml/skills/hs-web/SKILL.md）；bookmark.py / index.html 未动；版本未 bump（1.3.0 保持） |

## 维度评估

**commit 规范 §5** — 3/3 合规：
- 38e4ee0 `feat@web:` / 5e1e20a `tests@web:` / 197c27a `docs@web:` — type@scope 格式正确，scope 非空
- 分组按属性无混批：--domain + 校验 → feat@web；17 测试 + skills 5→6 → tests@web；skill 推广 + 文档 + spec 版本 → docs@web
- 3 条 type 均在项目历史类型集（feat/test/docs），scan-commits.py 无枚举缺口

**命名规范 §1** — 合规：
- 新增 `skills/hs-web/SKILL.md` kebab-case，frontmatter name 与目录名一致
- 报告文件名 kebab-case；diff 无 /Users 字面路径（0 hits）

## 安全事项

| # | 严重度 | 说明 | 状态 |
|:--|:------|:-----|:-----|
| SEC-023-1 | 🟢（记录） | `--domain` 注入 `Config().domain` 到 `shell=True` 命令（cli.py:1707），值仅双引号包裹，`set_domain` 无校验（`set_port` 有 1024-65535 校验）。双引号可挡 `;`/`&&`/`\|`/空格/换行，但 `"`、`$(...)`、反引号仍可破出。**攻击面 = 用户自有 config.json（无任何外部输入流入），与 `svc['cmd']` shell=True 同类（design 2C 明示语义）**；且 `svc['cmd']` 本身即 shell=True 透传，`--domain` 未新增任何权限边界（用户本可经 `--cmd` 直接写任意命令）。建议 `set_domain` 补域名字符集校验（如 `[a-zA-Z0-9.-]*`，拒绝 `"`/`$`/反引号/`;`）作 defense-in-depth | 记录 |
| SEC-023-2 | 🟡 | `~/.http-server.cli/services.json` 存在**第三条 `dk` 测试残留**（cmd `dk server start --daemon --open`，无 use_domain 字段，created 2026-08-27T08:10:11），与审计项 9「daily.checker + jaden.tech 两条 intact（demo-cl002 已清理）」不符 —— ops 手工 --domain 实测后 demo-cl002 已清但 `dk` 未清。非安全缺陷（dk 为真实命令，运行 `hs web dk` 等价于 daily.checker 面板；无 use_domain 字段 `svc.get('use_domain')` 返回 None 向后兼容不崩）。**修复：`hs web remove dk`（一条命令，非代码改动）** | ⏳ 待 ops 清理 |

> **设计确认（不列为发现）**：`_web_run` 的 `subprocess.run(cmd_line, shell=True)`（cli.py:1708）承接 CL001 设计 2C 明示语义，`--domain` 注入仅扩展现有 shell=True 面（用户自有 config + 用户自有 services.json，无外部输入）。diff 全量扫描：密钥/凭证/bearer//Users/eval/os.system 均 0 hits，shell=True 仅此一处。

🔴 0 项 / 🟡 1 项（SEC-023-2 注册表残留，本批范围内）/ 🟢 1 项（SEC-023-1 记录）。无跨域/认证/数据流缺陷，不触发人工通知规则。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 | −0 |
| 🟡（SEC-023-2） | −5 |
| 🟢（SEC-023-1 记录） | −0 |
| **得分** | **95 / 100 → Rating A** |

## 结论

**✅ PASS（95/100, A）** — 10 项审计 9 项全过 + 1 项（注册表状态）部分通过。三线全部落地：①--domain 入参（add store_true / update --no-domain 优先清除 / 执行注入 `--domain "<config.domain>"` / json `cmd_effective`），mock 断言 + 源码逐行核验双证；②hs-web skill 推广（SKILL.md frontmatter 合法、`hs prompt` 6 篇含 hs-web、镜像与源一致、test_prompt 6 全等）；③CL001 遗留三项全闭合（SEC-022-1 web 子命令名冲突拦截、SEC-022-2 services.json 三类形状校验 → DataCorruptionError、OBS-3 spec.yaml version 1.3.0 + 输出串修正）。459 测试全绿零回归（features.md 同步），版本四同步（__version__ = spec.yaml = `hs version` 实测 1.3.0）。范围控制到位（bookmark/index 未动，版本未 bump）。1×🟢 记录（SEC-023-1）+ 1×🟡（SEC-023-2 注册表 `dk` 残留，`hs web remove dk` 一条命令清理，非代码改动）。**commit audit@review + push（origin/main 推进至 197c27a）**。

## 待确认清单

| □ | 项 | 类别 |
|:--|:---|:-----|
| □ | **SEC-023-2（🟡 待 ops 清理）**：`~/.http-server.cli/services.json` 第三条 `dk` 测试残留，执行 `hs web remove dk` 清理（保留 daily.checker + jaden.tech 两条 intact） | 🟡 待清理 |
| □ | SEC-023-1：是否在 `set_domain` 补域名字符集校验（拒绝 shell 元字符），作 defense-in-depth | 🟢 记录项 |

## CL001 待确认清单闭环

| 项 | CL001 状态 | CL002 闭环 |
|:--|:-----------|:-----------|
| SEC-022-1（web 子命令名未拦截） | 🟢 记录 | ✅ 已修（cli.py:1272 `_WEB_SUBCOMMANDS` + cli.py:1349 冲突判断扩展，测试 2 例） |
| SEC-022-2（合法 JSON 错误形状裸 traceback） | 🟢 记录 | ✅ 已修（services.py:53-69 三类形状校验 → DataCorruptionError，测试 3 例） |
| OBS-3（spec.yaml version 1.1.0 既有漂移） | 🟡 待确认 | ✅ 已修（spec.yaml:2 version 1.3.0 + L291 输出串修正 `http-server v1.3.0`） |

# HTTP-SERVER-CL001 hs web 跨项目 Web 服务注册管理 — review报告 v1.0

> 日期: 2026-08-27
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 审计对象: 3 commits（2528128, 61d8ed7, 0a8e57d），基底 origin/main 99e104b
> review维度: 提交审计（审计规范 §6 + commit规范 §5 + 命名规范 §1）+ 功能实测
> 闭环: HTTP-SERVER-CL001 — hs web 一级子命令（ServiceStore + CLI 全套 + 版本 1.3.0）

## 数据验证（11 项全过）

| # | 验证项 | 方法 | 结果 |
|:--|:-------|:-----|:-----|
| 1 | 功能完整性：add/list/show/remove/update/`<name>`/help 全可用 + `--json` 信封 | 源码 cli.py:1271-1702 六函数 + test_web 64 例 + 实测 `hs web list/show --json` | ✅ 六子命令齐全；信封 `command` = web-add/web-list/web-show/web-remove/web-update/web-run 逐名一致 |
| 2 | 执行语义四分支：url 可达跳过 / 不可达执行 / `--no-probe` 强制 / 找不到 exit 1 | test_web run 类 10 例 + 实测 `hs web nonexistent` | ✅ `test_running_skips_cmd`（mock_run 未调用）/`test_unreachable_executes_cmd`/`test_no_url_skips_probe`/`test_no_probe_always_executes` 全绿；实测 `hs web nonexistent` → stderr `service 'nonexistent' not found` + `Available: daily.checker, jaden.tech` + **exit 1** |
| 3 | open 策略四态：url/cmd/both/none | cli.py:1666（探测命中）/1681（执行后）+ test_open_mode_* 4 例 | ✅ none 不开 / cmd 不开（命令自带 -o）/ both 命中也开 / url 默认开 |
| 4 | 启动后确认：url/both 策略执行 cmd 后 wait_url_reachable(10×0.3s) 再 open；cmd 非 0 退出码 warning 不阻断 | cli.py:1681-1702 + test_cmd_nonzero_exit_warns | ✅ `wait_url_reachable(url)` retries=10 delay=0.3（utils.py:273）；`result.returncode != 0` → stderr `⚠️ Cmd exited with code N`，不 raise 不 exit |
| 5 | 存储隔离：services.json 独立 + ensure_storage + DataCorruptionError + url 空串归一 None | utils.py:26/91-92 + services.py:40-49 + test_add_empty_url_normalized | ✅ `SERVICES_PATH=~/.http-server.cli/services.json`（与 bookmarks.json 并列独立）；`ensure_storage` 初始化 `{'services': []}`；损坏抛 `DataCorruptionError`；`url or None` 归一 |
| 6 | 校验：name 复用 bookmark 规则 + cmd 非空 + open_mode 四态 + url http(s):// + name 不与内置命令冲突 | services.py:52-91 + cli.py:1342 + test_web validation 12 例 | ✅ name `[a-zA-Z0-9][a-zA-Z0-9._-]*` 最长 128；cmd 非空；open_mode ∈ cmd/url/both/none；url `^https?://`；`parsed.name in _COMMANDS` 拦截内置命令（实测 `hs web add list` → `'list' conflicts with built-in command`） |
| 7 | 零外部依赖：探测用 urllib | pyproject.toml + utils.py:263-285 | ✅ pyproject `[project]` 无 dependencies 段；`url_reachable` 用 `urllib.request.urlopen`（标准库）；全 diff 无新 import 第三方包 |
| 8 | 测试：test_web 64 例 + 全量零回归 | `.venv/bin/python -m pytest -q` | ✅ **442 passed in 1.56s**（features.md:122 已同步「13 个测试模块，442 个测试用例」） |
| 9 | 文档同步：CHANGELOG 1.3.0 / features.md / README×2 / `__version__` 1.3.0 | grep 各文件 + `hs version` | ✅ CHANGELOG.md:3 `## 1.3.0 (2026-08-27)` + hs web 节；features.md:40 Web 服务注册节 + :80 services.json；README.md:171-185 / README.zh.md:171-185 Web 服务注册节双端对称；`__init__.py:26` = '1.3.0'；`hs version` 实测 `http-server v1.3.0` |
| 10 | 注册表状态：daily.checker + jaden.tech 两条不得删除 | 实测 services.json（pytest 前后两次读取） | ✅ daily.checker（url `http://127.0.0.1:5001`, open=url）+ jaden.tech（url null, open=cmd）两条 intact；conftest.py:57 monkeypatch 隔离，pytest 不触碰真实文件 |
| 11 | 全局薄壳：~/.local/bin/web | stat + `web list` 实测 | ✅ mode 755，内容 `exec hs web "$@"`；`~/.local/bin/web list` 输出 2 service 且 **exit 0** |

## 维度评估

**commit 规范 §5** — 3/3 合规：
- 2528128 `feat@web:` / 61d8ed7 `tests@web:` / 0a8e57d `docs@web:` — type@scope 格式正确，scope 非空
- 分组按属性无混批：ServiceStore+CLI+版本 → feat@web；64 测试 → tests@web；README/features/CHANGELOG → docs@web
- 3 条 type 均在项目历史类型集（feat/test/docs），无 feat@/test@ 枚举缺口（OBS-2 已于 skill v1.8.0 闭合）

**命名规范 §1** — 合规：
- 新增 `src/http_server_cli/services.py` / `tests/test_web.py` 均 snake_case / test_ 前缀，符合项目约定
- 报告文件名 `http-server-cli-web-registration-audit-v1.0-20260827.md` kebab-case
- 无 /Users 字面路径（diff 0 hits）

## 安全事项

| # | 严重度 | 说明 | 状态 |
|:--|:------|:-----|:-----|
| SEC-022-1 | 🟢（记录） | name 冲突校验仅覆盖顶层命令（`_COMMANDS`：start/list/status/kill/config/.../web），**未覆盖 web 子命令名** add/show/remove/update。实测 `hs web add show --cmd 'echo hi'` 注册成功，但 `hs web show` 恒被解析为 show 子命令 → 该服务永远无法经 `hs web <name>` 运行（非安全，UX 遮蔽，本地工具无注入面） | 记录，待确认是否扩展校验 |
| SEC-022-2 | 🟢（记录） | services.json 为「合法 JSON 但错误形状」（如 `[1,2,3]` / `"str"`）时，`_read_all` 走 `raw.get('services', [])` 抛未处理 `AttributeError`（裸 traceback），非 `DataCorruptionError`。损坏检测仅覆盖「JSON 语法错」与「空 dict + 非空文件」两类。工具自身原子写（write_json）不会产出该形状，仅手工篡改可触发（健壮性，非安全） | 记录，待确认是否补形状校验 |

> **设计确认（不列为发现）**：`_web_run` 使用 `subprocess.run(svc['cmd'], shell=True)` 透传（cli.py:1678）为本闭环用户决策（探讨 2C）明示语义。攻击面界定：cmd 仅来源于用户自有 `~/.http-server.cli/services.json`（`hs web add` 自行写入），无任何外部输入流入；name 经白名单正则约束（不可含 shell 元字符/路径分隔），url 经 `^https?://` 前缀约束且仅用于 urllib 探测与 `webbrowser.open`（list-args，无 shell）。单用户本地工具边界明确，无注入面。diff 全量扫描：密钥/凭证/bearer//Users/eval 均 0 hits，shell=True 仅此一处（设计语义）。

🔴 0 项 / 🟡 0 项（本批范围内）/ 🟢 2 项（记录，不扣分）。另 1 项 🟡 待确认（见下 OBS，属本批范围外、既有漂移）。无跨域/认证/数据流缺陷，不触发人工通知规则。

## 评分

| 项目 | 扣分 |
|:-----|:----|
| Base | 100 |
| 🔴 | −0 |
| 🟡（本批范围） | −0 |
| 🟢（SEC-022-1/2 记录） | −0 |
| **得分** | **100 / 100 → Rating A** |

## 结论

**✅ PASS（100/100, A）** — 11 项审计全过。hs web 一级子命令功能完整（六子命令 + help + 六信封 command 逐名一致）；执行语义四分支与 open 策略四态均以 mock 断言 + 运行时实测双证（含 `hs web nonexistent` exit 1 + 可用列表、`--no-probe` 强制执行、cmd 非 0 退出码 warning 不阻断）；存储隔离 + 损坏检测 + url 空串归一 + 全量校验到位；零外部依赖（urllib 探测，pyproject 无 dependencies）；442 测试全绿零回归（features.md 13 模块/442 同步）；CHANGELOG/features/README×2/`__version__` 四同步（`hs version` 实测 1.3.0）；注册表两条 intact（pytest 前后一致，conftest 隔离不触碰真实数据）；全局薄壳 `web` 可执行。2×🟢 记录项不扣分。**commit audit@review + push（origin/main 推进至 0a8e57d）**。

## 待确认清单

| □ | 项 | 类别 |
|:--|:---|:-----|
| □ | SEC-022-1：是否扩展 name 冲突校验至 web 子命令名 add/show/remove/update（当前仅拦顶层命令） | 🟢 记录项 |
| □ | SEC-022-2：是否在 `_read_all` 补「JSON 形状校验」（合法 JSON 非 dict → DataCorruptionError，替代裸 traceback） | 🟢 记录项 |
| □ | **OBS-3（🟡 待确认，本批范围外）**：`http-server.cli.spec.yaml` version 字段（L2）与「version 命令」场景（L291 `输出 http-server.cli v1.1.0`）仍停在 **1.1.0**，落后于 1.2.0 与 1.3.0 两次 bump；且场景输出串 `http-server.cli` 与实测 `http-server`（cli.py `_cmd_version` 输出 `http-server v{version}`）不一致。该漂移为**既有**（CL-SEC20「五处一致」亦未含 spec.yaml），本批 3 commit 未触碰 spec.yaml（diff stat 无此文件）。是否后续 `docs@spec` 同步 version 字段 + 场景输出串？ | 🟡 待确认 |

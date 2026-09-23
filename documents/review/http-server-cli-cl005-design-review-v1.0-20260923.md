# HTTP-SERVER-CL005 设计评审 — review 报告 v1.0

- 件号：`documents/review/http-server-cli-cl005-design-review-v1.0-20260923.md`
- 被审对象：`documents/http-server-cl005-hardening-design-v1.0-20260923.md`（commit `70c7a3d`，293 行）
- 范围：CL004 批遗留四项 —— O1 输出通道 / O3 `hs web` 退出码 / O5 目录级启动锁 / O6 派发件模板（D1–D4 + D9 版本口径 + §6 测试/断言设计）
- 性质：设计评审（审可执行性 / 判据完备性 / 回归风险 / 测试断言设计），非实现审计
- 基线核验（评审前提）
  - `git status --porcelain` 为空（树 clean，仅设计件新增）—— **评审前提未被破坏**，首段无需标注异常。
  - `git rev-list origin/main..HEAD` = 1（设计件 `70c7a3d`，未 push）。
  - `hs version` → `http-server v1.4.0`（设计口径 1.4.1 未实施，符合预期）。
  - `PYTHONPATH=src python3 -m pytest tests/ -q` → **557 passed**（与基线一致）。
- 结论：**CONDITIONAL_PASS**（78 / 100，Rating B）—— 4 项 🟡 必改（F-1~F-4）+ 9 项 🟢 记录（R-1~R-9）。方向正确、判据框架完备，但锁机制存在 2 处正确性缺口、web 退出码分类自相矛盾、测试同步计划漏点，须出 v1.1 后复审。

---

## 一、D1 输出通道（`eprint` → stderr + `print_msg` → stdout）

### 审项 1 — 语义纠正可行性

实证命令：`read_file src/http_server_cli/utils.py:33-38`

实测输出：
```
33: def eprint(msg: str, emoji: str = '') -> None:
34:     """智能打印，自动匹配 Emoji 前缀"""
35:     if emoji:
36:         print(f'{emoji} {msg}')        # ← 无 file= ⇒ 默认 stdout
37:     else:
38:         print(msg)
```

判定：✅ 成立。现状确为 stdout（`print` 无 `file=`）。改为 `print(..., file=sys.stderr)` 签名不变（`msg: str, emoji: str = ''` → `None`），外部零导入（`grep` 确认仅 `cli.py`/`server.py`/`utils.py` 仓内使用）。新增 `print_msg` 对称实现 stdout。可行。

### 审项 2 — 64 调用点判定规则可执行性（重点）

实证命令：`grep -rn "eprint(" src/`（全文 64 处匹配，含 `def eprint` 行 1 处）

实测输出（调用点计数）：`utils.py` 64/68/73 共 **3** 处；`cli.py` 28 处；`server.py` 32 处。合计 **63 处**调用点（非设计自述的 64——设计将 `utils.py` 计为 4，多计 1）。

判定：🟡 规则本身可执行（产物/失败·警告·清理 二分清晰），但存在 3 个灰区需在 §4.1 表显式定案：

| 调用点 | 通道判定 | 理由 | 灰区 |
|:--|:--|:--|:--|
| `server.py:189` `eprint(err,'❌')`（index_page 校验失败） | stderr | 校验失败=错误 | 无 |
| `server.py:204`（路径不存在） | stderr | 失败 | 无 |
| `server.py:357`（端口漂移 `🔀`） | stderr | 自动分配通知=警告 | 轻微（倾向 stderr） |
| `server.py:464` `Browser opened 🌐` | **灰区** | 成功副作用通知 vs 产物 | 需定案 |
| `server.py:473/478/481/486/496`（`Press Ctrl+C`/`Log tail stopped`/`Foreground mode`/`Interrupt`/`Service closed`） | **灰区** | 交互式提示 vs 产物 | 需定案；且属 `--daemon`/`foreground` 前台路径（见审项 4） |
| `server.py:519/520` `No running HTTP services`/`Use hs start...`（`hs list` 空） | **灰区** | 空清单=产物 还是 状态提示；决定 `hs list | wc -l` 语义 | 需定案 |
| `server.py:545` `Total N HTTP services`（list 表头） | stdout | 产物清单 | 无 |
| `cli.py:196/218` `Default port/domain set to...`（set 成功） | stdout | 产物 | 无（`test_cli.py:1046` 依赖 stdout，已由 print_msg 承接） |
| `cli.py:188/202/224`（set 错误） | stderr | 失败/未识别 | 无（`test_cli.py:1052` 已列改判） |
| `cli.py:1911` `Unknown command` | stderr | 失败 | 无 |
| `cli.py:730/971` `dashboard/MCP stopped 🛑` | stdout | 停止结果=产物 | 无 |
| `server.py:519/520` 外，`server.py:607` `Port N in use`（status 诊断） | stderr | 诊断 | 无（但同块 `print()` 提示见 R-9） |

判定：规则可执行，但设计未给出「空清单/交互提示」两类灰区的显式分类，且自述「64 处」与实测「63 处」不符（R-1）。

### 审项 3 — 隐藏回归（依赖 stdout 的既有测试/管道）

实证命令：`grep -rn "captured\.out\|\.out" tests/`（聚焦 eprint 产文断言）

实测输出（受影响断言）：
```
tests/test_utils.py:222   assert 'migration failed' in captured.out   ← _migrate_legacy_data (utils.py:68-73)
tests/test_server.py:180  assert 'No running HTTP services' in captured.out  ← list 空 (server.py:519)
tests/test_server.py:336  assert 'No running services' in captured.out       ← kill 空 (server.py:785)
tests/test_cli.py:296     assert 'No history records' in captured.out         ← history 空 (cli.py:519)
tests/test_cli.py:1046    assert 'Default domain set to jaden.local' in .out  ← set 成功 (cli.py:218)
tests/test_cli.py:1052    assert 'domain must match' in .out                  ← set 错误 (cli.py:212)
```

判定：🟡 设计 §4.1 仅列出 `test_cli.py:1052`，**漏掉 `test_utils.py:222`（migration full-failure）**——`eprint` 改 stderr 后该断言必红，需同步改 `.out`→`.err`（F-4）。`test_server.py:180/336` 与 `test_cli.py:296`（空清单/空历史）取决于审项 2 的灰区分类：若判「产物→stdout」则测试不红；若判「状态→stderr」则三处全红。设计未显式定案这两类，属测试同步计划的不确定点。

### 审项 4 — 三态契约完整性

实证命令：读 `server.py:466-496`（json/url 提前 return 与 daemon/foreground 块）

实测输出：
```
466: if json: return True       # json 模式跳过交互行为
469: if url_only: return True   # url 模式跳过交互行为
472: if daemon: subprocess.run(['tail','-f',log_path])  # tail 子进程直接继承 stdout，非 eprint/print_msg
480: if foreground: proc.wait() ...
```

判定：🟡 契约表 §3.1 覆盖了「默认/`--url`/`--json`」三态 stdout 形状，但 **`--daemon` 前台 tail 与 `foreground` 两模式未列明**：
- `--daemon`：`tail -f` 子进程 stdout 直接透传日志内容，**不经 `eprint`/`print_msg`**，因此不在 64 点审计范围内，D1 的「函数层面消灭信封污染」承诺对这条 stdout 路径不成立（好在 json/url 提前 return，仅默认模式触发）。
- `foreground`：`proc.wait()` 期间 runner 的 stdout/stderr 已在 Popen 时重定向到 log 文件（`server.py:369`），故无 stdout 污染；但交互提示（`Press Ctrl+C`/`Service closed` 等）通道未定案。
- 设计 §3.1「默认模式 stdout = 启动信息块」与 `tail -f` 日志透传是否计入「产物」未声明。

---

## 二、D2 `hs web` 退出码

### 审项 5 — 分支表是否穷尽

实证命令：读 `cli.py:1330-1852`（web 段全量）+ `services.py:129-231`（store.add/update 抛错面）

实测输出（对照设计 §1.2 表逐分支）：

| 分支 | 现有 rc | 设计目标 | 表内是否列出 | 结论 |
|:--|:--|:--|:--|:--|
| `add` 缺 `--cmd`（1391-1397） | 0 | 2 | ✅ 已列 | 一致 |
| `add` 名非法/冲突（1399-1412） | 0 | 2 | ✅ 已列 | 一致 |
| `add` `--open`/`--url` 非法（1415-1428） | 0 | 2 | ✅ 已列 | 一致 |
| `add` `--port/--no-port` 互斥（1429-1435） | 2 | 2 | （CL004 已改） | 已一致 |
| `add` store.add `ValueError`（1466） | 0 | 表内写「1 运行期」 | ⚠️ 分类错 | **F-3** |
| `add` `DataCorruptionError`（1471） | 0 | 1 | ✅ 已列 | 一致 |
| `list` `DataCorruptionError`（1496） | 0 | 1 | ✅ 已列 | 一致 |
| `show` 名不存在（1571-1577） | 0 | 1 | ✅ 已列 | 一致 |
| `remove` 名不存在（1621-1633） | 0 | 1 | ✅ 已列 | 一致 |
| `update` 名不存在（1667-1673） | 0 | 1 | ✅ 已列 | 一致 |
| `update` `ValueError`（1750） | 0 | 表内写「1 运行期」 | ⚠️ 分类错 | **F-3** |
| `run` `DataCorruptionError`（1783-1788） | 0 | （D2 文「运行期→1」隐含） | ❌ 表内未列 | 缺口 |
| `run` 名不存在（1790-1799） | 1 | 1 | ✅ 已列 | 已一致 |
| `run` cmd 失败（1850-1851） | **0** | D2 文「探测失败且 cmd 失败→1」 | ❌ 表内未列 | 缺口（**F-3**） |
| `web` 无子命令（1776-1778 → `_web_help`） | 0 | 0（保持） | ✅ 已列 | 一致 |

判定：🟡 表未穷尽。缺 `_web_run` 的 `DataCorruptionError` 与 **cmd 失败分支**（`cli.py:1850` 现仅 `print('⚠️ Cmd exited with code ...')` 到 stderr，仍 `return` rc=0）两处。其中 cmd 失败分支最实质：D2 正文承诺「探测失败且 cmd 失败→1」，但 §1.2 表无此条目，且 JSON 模式该路径仍输出 `success=True, status='started'`（`cli.py:1836-1845`，信封语义与 cmd 实际失败矛盾）。

### 审项 6 — 判定口径自洽

实证命令：读 `services.py:129-231`（store.add/update `ValueError` 语义）

实测输出：`store.add` 抛 `ValueError` 的场景含 `"service '{name}' already exists"`（无 `--force`，`services.py:162`）、`"service cmd cannot be empty"`（`--cmd ''`）、`open_mode/url/port` 非法。`store.update` 同理（`--cmd ''`、`url/open/port` 非法）。

判定：🟡 **自相矛盾**。设计 D2 规则「用法错误（…名非法、冲突…）→ 2」，但 §1.2 表把 `add/update` 的「store 异常」整体归为「1 运行期」。而 `store.add/update` 抛的 `ValueError` 全部是**用法/校验类**（名已存在=冲突、cmd 空、值非法），按设计自己的规则应 exit 2，非 1。唯一的「运行期→1」只应是 `DataCorruptionError`。表需拆分：`ValueError → 2`（用法）、`DataCorruptionError → 1`（运行期）。参照口径 CL003 D14（`hs start`）自洽（`UsageError→2` / `return False→1`），本表未对齐（F-3）。

### 审项 7 — JSON 模式信封顺序

实证命令：读 `cli.py:1391-1397`（add 缺 cmd json 分支）与 `utils.py:368-384`（json_output 实现）

实测输出：
```
1393: if json_mode: json_output(False, cmd, error=err)   # 先出信封
1395: else: print(f'❌ {err}', file=sys.stderr)
1397: return                                             # 当前 rc=0（本批改 sys.exit(2)）
...
384: print(json.dumps(payload, ensure_ascii=False, indent=2))   # indent=2 ⇒ 多行输出
```

判定：🟢/🟡 顺序无风险（先 `json_output` 再 `sys.exit` 正确，stdout 仅信封）。但两点：
- 设计 §3.2「stdout 仅一行可解析」与 `json_output` 的 `indent=2`（多行）措辞冲突。若实现者按「一行」字面改掉 indent，属未声明的契约变更；正确表述应为「仅含一个可 `json.loads` 的 JSON 文档」（R-2）。
- `_web_run` cmd 失败路径的 JSON 信封仍 `success=True`（1836-1845），与退出码 1 语义不一致，见 F-3。

---

## 三、D3 目录级启动锁（重点）

### 审项 8 — 并发唯一性论证 + 未覆盖竞态

实证命令（`/tmp` 最小实验，20 线程竞争同一 `O_CREAT|O_EXCL` 锁文件）：
```
winners=1 ids=[0] lock_content={"pid": 0}
partial-write: second open correctly got FileExistsError (file exists but empty)
```

判定：🟡 **O_EXCL 原子性成立**（20 线程仅 1 赢家），但设计漏 3 个竞态：

1. **「无 pid / 不可解析 ⇒ 删锁重试」的 mid-write 竞态（最严重）**：设计 D3 判据 1 把「锁文件不可解析 / 无 pid」判为 stale 立即删锁。但锁协议是 `O_EXCL 创建 → 写内容 → 关闭 fd`，三者非原子。进程 A 在 `O_EXCL` 成功但**尚未写入内容**时，进程 B 读到空文件 → 判 stale → 删 A 的锁 → B 自建锁。此时 A 仍持有效 fd（指向已 unlink 的旧 inode）继续启动 ⇒ **A、B 双双进入启动流程，锁失效**。上例「partial-write: 空文件仍 FileExistsError」直接证实空锁文件会阻塞但可被误判 stale。修复方向：对「无 pid/不可解析」的锁，须先看锁龄（mtime）——若 < 一个小阈值（如 1s，或直接 < LOCK_TTL），视为「holder 正在写入」，走等待而非删锁。（F-1）
2. **release 与 acquire 交错**：设计 `finally` 删除锁文件（best-effort）。若进程 A 删锁后进程 B 恰好 `O_EXCL` 新建成功，无问题；但若 A 的「删除」与 B 的「O_EXCL 创建」之间还有 C 读 stale 删 B 的锁，回归竞态 1。设计未说明 release 是否需校验「删除的是自己创建的锁」（token/pid 匹配）——当前 `release(lockpath)` 直接 unlink，无归属校验。
3. **registry 写入与锁释放先后**：设计 `finally` 释放锁，注册（`registry.add`）在 start() 体内、释放之前 ⇒ 正确（先注册后释放）。但若 `registry.add` 抛异常，`finally` 删锁后 registry 无记录 + runner 已 Popen ⇒ 孤儿。设计未声明 registry.add 失败时的 runner 回滚（与 CL004 既有「判 stale 先终止进程组再清登记」的孤儿防护是否衔接）。

另：**锁键在 html 文件快捷方式的发散**（F-1 一部分）——设计 §4.3「`abs_path = resolve_path(path)` 之后 acquire」，但 `server.py:165-168` 会把 html 文件路径改写为父目录。实测锁键发散：
```
resolve_path(file) = .../tmpto_sl2vo/index.html   → lock_key 1d44347659940b0c
resolve_path(dir)  = .../tmpto_sl2vo             → lock_key 2bdca8c84a3bdd5a
```
即 `hs index.html` 与 `hs <dir>` 得到**不同锁**，混合调用时互斥失效。锁键必须以**html 提取后的最终 abs_path** 为输入。

### 审项 9 — stale 判据完备性

判定：🟢/🟡 四判据（无 pid / pid 死 / 超 TTL / token 不匹配）方向正确，反例如下：
- **pid 复用**：holder pid 死亡后被 OS 复用给新进程，`is_process_alive` 返回 True；若新进程 cmdline 恰含 `http_server_cli`/`hs`（token 很松，见 R-6），锁被误判「有效」→ 等待方 fail-closed（安全方向，但可用性受损）。设计「pid 复用由 token 校验拦截」只对 runner 的 `runner.py+abs_path` 精确匹配成立，对锁 holder（CLI 进程）的 `basename hs` 匹配**不成立**。
- **时钟回拨**：`started_at` 用 `timestamp()`（`datetime.now()` 墙钟，`utils.py:326-328`）。时钟回拨时 `age = now - started_at < 0`，永不超 TTL ⇒ TTL 判据失效，仅剩 pid 活性兜底。应改用 `time.monotonic()` 或锁文件 mtime 计时（R-5）。
- **部分写入**：写内容前崩溃 ⇒ 空/半文件，落入审项 8 竞态 1（「无 pid→删锁」误删 concurrent writer）。
- **`host` 字段用途不明**：锁内容 `{path, pid, started_at, host}` 的 `host` 在四条 stale 判据中均未使用，且 §3.3 伪码只写 `{path,pid,started_at}` 三字段（§2 与 §3.3 不一致，R-3/R-4）。

### 审项 10 — 等待路径交互

判定：🟢 方向正确，但与 CL003「幂等优先」顺序链需澄清。锁在「路径解析后、幂等判定前」获取：若服务**已运行**且首实例已释放锁（daemon/foreground 之外的首实例 return 后释放），第二实例 O_EXCL 成功 → 走 registry 幂等命中 rc=0，无「误判正在启动」。唯一「已运行被误判正在启动」发生在**首实例仍持锁**（`--daemon` tail 期间或 `foreground` proc.wait 期间）——此时第二实例 wait 路径轮询 registry，因首实例早已 `registry.add`（`server.py:411` 先于 tail/foreground 块 472/480），3.0s 内必命中幂等 rc=0，**不会误判**。故「已运行→正在启动」误判风险低，但前提是等待路径的幂等判定**必须复用 registry 就绪口径（含端口监听）**，而非仅看锁——设计已声明此口径，成立。

### 审项 11 — 失败路径退出码一致 + 执行顺序推演

判定：🟡 设计声称「路径不存在→rc1 / `-p` 用法错误→rc2 不被锁掩盖」，但「锁在 start() 最前」的放置使该承诺**在锁竞争下不成立**。现有顺序（`server.py`）：index 校验(180) → 路径存在(197) → 幂等判定(207) → `-p` 校验(310，越界 `raise UsageError`→exit 2) → Popen(365) → 注册(411)。锁若插在 `resolve_path` 后（最早位置），则「锁等待超时 exit 1」先于 `-p` 越界 `UsageError`（exit 2）与「路径不存在 return False」（exit 1）触发。推演：`hs <dir> -p 70000` 在另一实例持锁时 → 第二实例等待 3.0s 超时 → exit 1「正在启动」，而非应有的 exit 2。修复方向：**锁应收窄到临界区**（路径/index/`-p` 纯用法校验之后、`registry.find` 幂等判定之前），或至少把 `-p` 越界（`UsageError`）这类纯用法校验提升到锁获取之前（F-1）。

### 审项 12 — 异常安全（`finally` 与 `SystemExit`）

判定：🟢/🟡 设计用 `try/finally` 释放锁方向正确（`finally` 覆盖 `SystemExit`/`BaseException` 路径）。缺口：
- `finally` 覆盖范围未声明：start() 有 6 处 `return False`（index 校验/路径不存在/保留端口/端口占用/端口耗尽/启动异常）+ 1 处 `raise UsageError` + daemon/foreground 长阻塞。若 `finally` 只包「锁获取之后到注册」而不包早期 return（index/路径），需确保这些早期 return **也释放**（否则锁泄漏 30s TTL 自愈）。设计未给出 try 块的精确起止。
- `--daemon`/`foreground` 前台阻塞期间锁被长期持有（见审项 10），锁语义从「启动锁」退化为「会话锁」，虽无正确性危害（幂等兜底），但与「启动锁」命名/文档不符，应在设计声明。
- 测试进程被杀：`SIGKILL` 不触发 `finally` ⇒ 靠 TTL 30s + pid 活性自愈，最坏 30s，设计已声明，成立。

### 审项 13 — 常量与可测性

判定：🟢 设计声明 `LOCK_TTL/LOCK_WAIT/LOCK_POLL` 模块级可替换 + `lock_path(abs_path)` 可注入，方向正确。缺口：**未声明 `LOCK_DIR` 的 monkeypatch 方案**。锁路径 `~/.http-server.cli/locks/<sha1(abs_path)[:16]>.json` 是 `DATA_DIR` 派生常量；测试若用真实 HOME 会污染 `~/.http-server.cli/locks`，与 conftest 既有隔离（registry/services 走 tmp 目录）需对齐。设计 §6 测试 T12-T16 未说明如何注入 LOCK_DIR（是否 monkeypatch `utils.LOCK_DIR` / 传 `lock_dir` 参数）。建议在 §4.3 明确「LOCK_DIR 模块级常量 + 测试 monkeypatch」或「acquire 接受可选 lock_dir 参数」，并在 A8「locks/ 无残留」中明确残留判定基于注入目录（F-4 的一部分，测试隔离）。

---

## 四、D4 派发件 + D9 版本口径

### 审项 14 — 路径推导与既有命名一致

实证命令：`ls -1 cache/closed-loop/ | grep -E "CL00[345]"` + 读 `cache/review-prep/dispatch-http-server.cli-cl00{4,5}-*.sh`

实测输出（既有命名）：
```
usage:   20260922-http-server.cli-HTTP-SERVER-CL004-design-rereview{,,3,4}.json  / audit.json / design-review.json
dispatch-log: HTTP-SERVER-CL004-design-review-dispatch.log   (无 date/project 前缀，-dispatch.log 后缀)
```

判定：🟡 设计 D4 的推导式 `{date}-{project}-{code}-{step}{-round}.log/.json` 与既有命名 **多处不符**：
- **LOG 与 USAGE 命名不同源**：usage 是 `{date}-{project}-{code}-{step}.json`（date=YYYYMMDD 无横线、project=http-server.cli、code=HTTP-SERVER-CL004 大写），但 dispatch-log 是 `{code}-{step}-dispatch.log`（无 date/project、无 `-` 连 project）。设计把 `.log/.json` 用一个模板套，推导出的 LOG 会与既有 dispatch-log 不匹配（应分别定义 LOG 模板与 USAGE 模板）。
- **轮次词与 `--step/--round` 分解不符**：既有文件 `design-rereview`（第 1 轮，无后缀）、`design-rereview2/3/4`（**裸数字后缀，无 `-`**）。设计用法 `--step <步骤键> --round <轮次词>` 若实现为 `{step}-{round}` 会产出 `design-rereview-3`（多一个横线），与既有 `design-rereview3` 不符。轮次词规则（review/rereview{2,3,4}/audit）实际是「步骤键已含轮次」，而非独立 `--round` 后缀。
- **大小写陷阱（skill pitfall #19）**：`code` 在 usage 是大写 `HTTP-SERVER-CL005`，在 dispatch-log 也是大写，但 dispatch 脚本文件名是**小写** `dispatch-http-server.cli-cl005-...`。脚本须明确 code 参数大小写规范化，否则 LOG/USAGE 指回上一轮。
- **date 格式漂移**：既有 `20260922`（无横线）与更早 `2026-08-23`（有横线）并存，脚本须锁定 `YYYYMMDD`。
- 设计自述「手写/派生壳共 9 个」，实测 `cache/review-prep/` 下 cl003(3)+cl004(6)+cl005(1)=**10** 个（R-8）。

### 审项 15 — 自校验可测

判定：🟢 方向正确（缺 usage-file ⇒ 诊断 + exit 2；`--dry-run` 只打印）。缺口：设计 §6 T17 只断言「三路径推导正确 + 非法参数 rc≠0」，**未断言「真实派发产生非空 usage-file」的 pytest 可测版**——A9 提到「真实派发产生非空 usage-file」，但真实派发依赖 `hermes`/`pgrep` 环境，pytest 内不可复现。建议拆分：脚本的核心「路径推导 + 自校验逻辑」抽成可单测的纯函数/子命令（`--dry-run` 已可测），真实派发的 usage 非空核对留在 ops harness（A9）而非 pytest。设计未明确这一分层（R-7 延伸）。

### 审项 16 — 版本口径 1.4.1 vs 并入 1.4.0

实证命令：读 `CHANGELOG.md` 头部、`__init__.py:28-29`、`spec.yaml:2`

实测输出：`__version__ = '1.4.0'` / `__release_date__ = '2026-09-22'` / `spec.yaml version: 1.4.0` / `CHANGELOG` 最新条目 `## 1.4.0 (2026-09-22)`。

判定：✅ **1.4.1 独立小版本合理**。理由成立：1.4.0（CL003+CL004）已 PASS 99/100 且随时可发布，本批含行为变更（输出通道/退出码）+ 新增机制（启动锁），独立小版本利于回溯回滚。设计 D9 三条理由与 CHANGELOG/README 退出码小节增补计划齐备，五处同步落点（`__version__`/`__release_date__`/CHANGELOG/spec/features）明确。无阻断。

---

## 五、测试/断言设计（§6）

### 审项 17 — 无恒真断言

判定：🟢 逐条读 T1–T18/A1–A14，未发现「无论实现如何都成立」的恒真断言。可翻转性抽查：T12（并发 5 次 registry 1 条 + pid 同一性）依赖锁正确性——若锁失效（F-1 竞态），T12/A5 会红（registry>1 或 listener≠registry），故为真断言而非恒真。T13（伪造 holder=活 pid 且 cmd 含特征 → rc=1）可翻转（若实现未加锁则 rc=0）。A5 修前反证基线 `4679ee8`（CL004 收尾、锁未实施）恰当——取更早（`ef125b3`）反而引入 CL004 已修的其他竞态噪音，`4679ee8` 是「锁缺失但其余已修」的正确对照。判定成立。

### 审项 18 — 并发/时序纪律（A5）

判定：🟢 设计 A5 描述与 CL004 定案口径一致：就绪等待 ≤2s 轮询到 LISTEN、剔除幂等样本、最小有效样本数、pid 同一性（禁计数相等）、禁 `hs list --json` 当数据源、禁 `in` 子串归属。修前反证基线 `4679ee8` ✓（同上）。无新增违规。

### 审项 19 — 覆盖缺口 + 补测建议

判定：🟡 设计漏测以下点，建议补入 T/A 表：
1. `--daemon` 前台 tail 模式下的锁释放：tail 结束后锁是否释放（首实例 return → finally 释放）——现 T16 只测「启动后 locks/ 无残留」，未覆盖 daemon tail 阻塞后的释放。
2. `foreground` 模式下 runner 退出后锁释放。
3. **锁键 html 快捷方式**：`hs index.html` 与 `hs <dir>` 应得同一锁（F-1 修复后的回归断言）。
4. **mid-write 竞态**：伪造「空锁文件且 mtime 极新」→ 应等待而非删锁（F-1 修复后的回归断言）。
5. `hs dashboard`/`hs mcp` 是否受影响：二者不经过 `start()`（走 ManagedRegistry 独立路径，`server.py` 未见锁调用），设计应显式声明「dashboard/mcp 不纳入锁范围」，避免实现时误加。
6. 锁 holder 归属校验（release 只删自己创建的锁）——现无对应测试。
7. web 退出码的 JSON 模式矩阵（A4 已含「含 JSON 信封可解析」，但 `_web_run` cmd 失败的信封语义 `success=False` 未列）。

---

## 安全事项

- 🟡 **SEC-1（F-1 实质）**：锁机制「无 pid/不可解析→删锁」在 mid-write 窗口可致双重持有，破坏「至多一个赢家」的核心不变量。属并发正确性缺陷，非仅措辞。
- 🟡 **SEC-2（F-1 实质）**：锁键未按「html 提取后最终 abs_path」归一，`hs file.html` 与 `hs dir` 互斥失效，孤儿 runner 防护被绕过。
- 🟢 锁 holder 身份 token 采用 `basename hs`（过松，可被 pid 复用 + cmd 巧合命中），方向为 fail-closed（可用性受损，无越权）。
- 🟢 `shell=True`（`cli.py:1826` web run 透传）属设计语义，本批不改，无新增注入面。

## 评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| 合理性（方向正确性） | 22/25 | eprint 语义纠正 / 退出码三态 / O_EXCL 锁 / 派发模板方向全对 |
| 严格性（判据完备） | 18/25 | 锁 stale 判据与竞态、web 退出码分类、锁键归一有缺口 |
| 可执行性（落点清晰） | 20/25 | 落点基本齐备，锁放置/测试隔离/派发命名有未定项 |
| 回归风险控制 | 18/25 | 测试同步漏 test_utils.py:222、灰区分类未定案 |
| **合计** | **78/100** | Rating **B** |

## 结论

**CONDITIONAL_PASS**（78/100，B）。方向正确、判据框架完整，但存在 4 项 🟡 必改（2 项锁正确性、1 项退出码分类、1 项测试同步），须出 v1.1 后复审。本评审不提交、不 push。

### 🟡 必改清单（编号 + 落点 + 验证要求）

| # | 标题 | 落点 | 验证要求 |
|:--|:--|:--|:--|
| F-1 | 锁放置与 stale 判据两处正确性缺口 | 设计 §2 D3 / §3.3 / §4.3 | ①锁键按「html 提取后最终 abs_path」；②「无 pid/不可解析」改判锁龄<mtime 阈值→等待非删锁；③锁收窄到「用法校验后、`registry.find` 前」，保证 `-p` 越界仍 exit 2、路径不存在仍 exit 1；④release 增归属校验。补 T/A：html 快捷方式同锁、mid-write 等待、`-p` 越界不被掩盖 |
| F-2 | stale 判据反例（时钟回拨 / 字段不一致） | 设计 §2 D3 / §3.3 | `started_at` 改 `time.monotonic()` 或 mtime 计时；统一锁内容字段（去 `host` 或说明用途）；§2 四字段与 §3.3 三字段对齐 |
| F-3 | web 退出码分类自相矛盾 + 分支表未穷尽 | 设计 §1.2 / §2 D2 | `add/update` 的 `ValueError`（名已存在/cmd 空等）→ exit 2（用法），`DataCorruptionError`→exit 1（运行期）；补 `_web_run` `DataCorruptionError`→1 与 cmd 失败→1 两分支；cmd 失败时 JSON 信封 `success=False` |
| F-4 | 测试同步计划漏点 + 测试隔离缺口 | 设计 §4.1 / §6 | 补 `test_utils.py:222`（migration full-failure `.out`→`.err`）；显式定案「空清单/空历史」通道；明确 `LOCK_DIR` 的 monkeypatch/注入方案 |

### 🟢 记录清单（同批落点，非阻断）

| # | 标题 |
|:--|:--|
| R-1 | 调用点计数 63 处（cli 28/server 32/utils 3），设计自述 64 |
| R-2 | 「stdout 仅一行」与 `json_output(indent=2)` 多行措辞冲突，应改「仅一个可 `json.loads` 文档」 |
| R-3 | 锁内容字段 §2（4 字段）与 §3.3（3 字段）不一致 |
| R-4 | `host` 字段在四条 stale 判据中均未使用（死数据） |
| R-5 | `started_at` 墙钟计时，时钟回拨致 TTL 失效（并入 F-2 亦可） |
| R-6 | 锁 holder token `basename hs` 过松，fail-closed 可用性受限 |
| R-7 | D4 路径推导：LOG/USAGE 命名不同源、`--step/--round` 与扁平文件名不符、date 格式未锁定 |
| R-8 | 派发壳计数 10 个（设计自述 9） |
| R-9 | D1 审计仅覆盖 eprint 点，忽略裸 `print()` 诊断（如 `server.py:1798` "Available"、`server.py:607-614` status 占用块） |

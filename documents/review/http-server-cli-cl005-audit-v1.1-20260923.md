# http-server.cli CL005 实现审计报告 v1.1（round-2 复审）

- 件号：`documents/review/http-server-cli-cl005-audit-v1.1-20260923.md`（round-2 收口复审件；v1.0 报告保留不动）
- 上轮报告：`documents/review/http-server-cli-cl005-audit-v1.0-20260923.md`（CONDITIONAL_PASS 90/100，唯一 🟡 SEC-1 + 3×🟢 R-1~R-3）
- 设计依据：`documents/http-server-cl005-hardening-design-v1.2-20260923.md`（v1.2，§9.3 新增偏差 D3-3 / §9.7 记录项处置）
- 本轮被测对象（3 笔 rework commit）：`91ebea3`（fix@cli SEC-1 回滚）· `4cb256d`（test@cli T28/T28b + ops A16/A9）· `70df367`（docs@sync §9.3 D3-3 + §9.7/9.8 + 计数勘误 + R-1 版本元数据）
- 审计基线：HEAD `70df367`，本地 ahead 9（未 push），工作树 clean
- 修前反证基线：`4679ee8`（CL004 收尾，不变）
- 审计人：Security Reviewer（review profile）· 日期：2026-09-23
- 环境：macOS 26.6.2 · `hs` = conda py3.12.13 editable 安装（指向本仓 `src/`）· 全量测试经 `python -m pytest`（3.12.13 + xdist 3.8.0）

## 0 结论（前置）

**PASS（100/100，Rating: A）** —— 上轮唯一 🟡 必改 SEC-1 已闭合，3 项 🟢 记录（R-1/R-2/R-3）全部按期望处置；闭合面无新缺陷、无回归、无越界。上轮已 PASS 的 D1（63 点通道表）/ D2（退出码矩阵）/ D3 其余机制 / D4 模板 / 四同步，本轮复跑全量回归未发现可推翻证据，维持 PASS。

核心结论（逐条实证见 §二）：
- **SEC-1 闭合**：`registry.add` + `history.add` 合入同一 `try`，异常时 `_terminate_runner(proc.pid)` 回滚 + `url_only/json/默认` 三态报错 + `return False`（⇒ CLI 退出码 1）。独立复现（T28/T28b + ops A16）确认「不产生孤儿 / 锁已释放 / 退出码 1」三点成立。
- **差量判定（re-raise vs return False）**：判定为**语义等价且优于 re-raise**，采纳实现方案，不要求 re-raise（详见 §二 SEC-1 第 3 点）。
- **R-1/R-2/R-3**：版本元数据、§9.2/§9.5 计数、§9.7 口径均已按期望落地，独立复核与实测一致。
- **回归**：`pytest tests/ -q -n 4` = **592 passed**；`test_cl005_hardening.py` = **35 passed**（T1–T28b）；ops `cl005-verify.py` = **21/21 PASS**（A1–A17，含扩展 A16 = 归属 + 注册失败回滚）。
- **未越界**：本轮 rework 对 `src/` 的 diff 仅 `__init__.py`（版本元数据 4 行）+ `server.py`（注册段 try/except 33 行），无 `registry.py` / `MAX_PORT` / 保留端口改动。
- **残留**：`registry.json`（9 服务结构身份不变，仅 `last_access_at` 时间戳漂移，A13 口径内）/ `services.json` 逐字节一致 / `locks/` 空；无遗留 START runner/listener/锁。
- 🟢 观察（非 CL005、非阻断）：全量 pytest 会经 `test_dashboard.py::TestDaemonMode::test_daemon_mode_subprocess` 泄漏一个 daemon dashboard 孤儿进程（`serve(daemon=True)` 随机端口不回收），属**既有测试卫生问题**（该测试 commit 8a79b92 早于 CL005，本轮未触碰），与 CL005 判定无关，见 §三 OBS-1。

---

## 一、数据验证（独立复算）

| 项 | 实测 | 判定 |
|:--|:-----|:--|
| git HEAD | `70df367`（ahead 9，`git status` 空） | ✅ 与基线一致 |
| `hs version` | `http-server v1.4.1` | ✅ |
| 全量回归 | `python -m pytest tests/ -q -n 4` → **592 passed in 2.72s**（0 failed） | ✅（590 + T28/T28b 2 例） |
| 硬化用例 | `test_cl005_hardening.py` → **35 passed**（T1–T28b） | ✅ |
| 回滚用例 | `TestRegistryRollback` → **2 passed**（T28/T28b） | ✅ |
| ops harness | `scripts/cl005-verify.py` → **21/21 PASS**（A1–A17，117.1s） | ✅ |
| 既有 harness | A10 内：port-flag-verify.py **31/31** · port-residual-verify.py **13/13** | ✅ |
| rework src 越界 | `git diff cbe30ac HEAD -- src/` = 仅 `__init__.py`(4) + `server.py`(33)；`registry.py` 空 | ✅ 零越界 |

---

## 二、闭合面逐条实证

### 1. SEC-1（必改）— `registry.add`/`history.add` 失败回滚

**(1) 代码读审**（`src/http_server_cli/server.py:494-516`）：

`started_at` 之后，`self.registry.add(...)` 与 `history.add(...)` **合入同一 `try`**；`except Exception as e:` 分支：
- 无条件调用 `_terminate_runner(proc.pid)`（`server.py:509`）；
- 三态报错：`url_only` → `print('❌ Registry write failed (runner terminated): {e}', file=sys.stderr)`；`json` → `json_output(False, 'start', error=...)`（信封 `success=false`，stdout 可解析）；默认 → `eprint(...)`（stderr）；
- `return False`。

`_terminate_runner`（`server.py:93-103`）：`os.getpgid(pid)` + `os.killpg(pgid, SIGTERM)` → `time.sleep(0.5)` → 仍活则 `os.killpg(pgid, SIGKILL)`，与 `kill()` 语义（SIGTERM → 0.5s → SIGKILL 进程组）一致。因 `Popen` 用 `preexec_fn=os.setsid`（`server.py:455`），runner 即进程组组长，`killpg` 精确覆盖本次 runner。

锁释放：`start()` 的 `try/finally: release_start_lock(lockfile)`（`server.py:203-206`）独立于 `_start_locked` 内部返回路径，异常回滚后 `finally` 照常释放。✅

**(2) 独立复现**（不改工作树，可复跑）：

```
$ python -m pytest tests/test_cl005_hardening.py::TestRegistryRollback -q
2 passed in 0.01s
```

T28（`test_t28_registry_add_failure_terminates_runner`）：monkeypatch `Registry.add` 抛 `OSError('disk full')`，断言 ① `start(url_only=True) is False` ② `killed == [90001]`（`_terminate_runner` 收到本次 pid）③ `'Registry write failed' in captured.err`（stderr 文案）④ `lock_path` 不存在（锁已释放）。T28b（`test_t28b_history_add_failure_json_envelope`）：monkeypatch `HistoryStore.add` 抛 `OSError`，断言 ① `start(json=True) is False` ② `json.loads(out)['success'] is False` 且 `'Registry write failed' in error`（信封可解析）③ `killed == [90001]` ④ 锁已释放。两用例为真断言（非恒真空转），覆盖 `url_only`/`json` 两态 + registry/history 两写入口。

ops harness A16 复核（`scripts/cl005-verify.py:640-652`）：以 `pytest TestRegistryRollback -q -n 0` 复用上述证据，实测 `rollback_ok=True`（`2 passed`）。✅

**(3) 差量与判定（re-raise vs return False）**：

审计 v1.0 建议「`_terminate_runner` 后**再 re-raise**」；本批改为「`_terminate_runner` 后 `return False` + 三态文案」。独立判定：**语义等价，且优于 re-raise，采纳，不要求 re-raise。**

论证（三点设计要求逐一对照）：
- **不产生孤儿**：`_terminate_runner` 在 `except` 分支无条件先执行，re-raise 与 return 两案相同。✅
- **锁已释放**：由 `start()` 的 `finally` 负责，与 `_start_locked` 内如何返回无关，两案相同。✅
- **退出码 1**：`return False` 经 `_cmd_start`（`cli.py:288-295`）——`except UsageError: sys.exit(2)` 不命中（`OSError` 非 `UsageError`），`if parsed.url: sys.exit(0 if result else 1)`，`if result is False: sys.exit(1)`——三态恒 `exit 1`。✅
- **re-raise 的实际后果**：`OSError` 向上冒泡至 `main()`（`cli.py:1940` 无顶层 try）→ `__main__.py`（无 catch）→ Python 默认未处理异常处理器 → **dump traceback + 退出码 1**。即 re-raise 唯一实质差别是向用户泄漏 traceback，与设计 D14/CL003「运行期失败 → exit 1 + 干净文案」的意图相悖；`return False` 保留 `str(e)` 文案（如 `disk full`/`read-only fs`）已含关键诊断，不丢信息。故本实现更贴合设计意图，语义等价且对用户更友好。

影响面：无。设计 §9.3 偏差 D3-3 已明确记录此差异与理由（`server.py` 注释同口径）。

**(4) 真机侧证（可构造等价）**：进程内注入写盘失败（monkeypatch `Registry.add`/`HistoryStore.add`）即 T28/T28b 的等价证据，已在隔离数据目录验证「runner 被终止（`killed==[90001]`）+ 锁释放 + 无登记 + 无 LISTEN」。真机以只读 `registry.json` 构造会污染真实数据目录（违反纪律），故不额外执行；T28/T28b 在 monkeypatch 层直接断言「终止 + 无孤儿 + 锁释放」，覆盖设计 D3.5 全部要点，等价成立。✅

### 2. 记录项处置

**R-1（版本元数据）**：`src/http_server_cli/__init__.py:25` docstring `Version: 1.4.1(2026-09-23)`；`:28-29` `__version__='1.4.1'` / `__release_date__='2026-09-23'`。`hs version` 实测 `http-server v1.4.1`。✅

**R-2（计数勘误）**：设计 §9.2（`documents/...v1.2.md:466`）改「13 处 web 单测…（`test_web.py` 12 处 + `test_port_flag.py` 1 处）」；§9.5（`:503`）「web 单测 SystemExit | 未列 | **+13**」。独立复算：`git diff 4679ee8 HEAD -- tests/test_web.py | grep -c '^+.*raises(SystemExit)'` = **12**；`test_port_flag.py` = **1**；合计 **13**。与设计口径一致。✅

**R-3（usage 口径）**：设计 §9.7 R-3 行（`:524`）定口径「usage-file 缺失/空 = 软告警（写日志 + stderr）；提示词缺失/空才是 exit 2（派发前硬校验）」，并明示「§2 D4 原文不改（历史件）」。实现核对 `scripts/review-dispatch.sh`：提示词 `[ ! -s "$PROMPT_ABS" ]` → `echo ... >&2; exit 2`（`:94-96`，硬校验）；usage-file 空 → 派发壳内 `[ ! -s "$USAGE" ]` 仅写 `>> "$LOG"`（`:125-127`）+ 外层 `echo ... >&2` 告警不退出（`:149-151`，软告警）。✅

---

## 三、安全事项（findings）

| # | 级别 | 标题 | 落点 | 处置 |
|:--|:--|:--|:--|:--|
| SEC-1 | ✅ 闭合 | D3.5「`registry.add`/`history.add` 抛异常 ⇒ `_terminate_runner` 回滚 ⇒ 不产生孤儿」已实现 | `server.py:497-516`（+ `:93-103` `_terminate_runner`） | 本轮已修（T28/T28b + A16 实测） |
| R-1 | ✅ 闭合 | `__release_date__`/docstring 版本元数据 | `__init__.py:25,28-29` | 已修（1.4.1 / 2026-09-23） |
| R-2 | ✅ 闭合 | §9.2/§9.5 计数勘误 | 设计 §9.2:466 / §9.5:503 | 已修（12+1=13 / +13） |
| R-3 | ✅ 闭合 | usage-file 软告警 vs 提示词 exit 2 口径 | §9.7:524 + `review-dispatch.sh:94-96,125-127,149-151` | 已定口径（§2 D4 历史件不改） |
| OBS-1 | 🟢 | 全量 pytest 经 `test_dashboard.py::TestDaemonMode::test_daemon_mode_subprocess` 泄漏 daemon dashboard 孤儿（`serve(port=随机, daemon=True)` 不回收） | `tests/test_dashboard.py:246-263`（commit 8a79b92，非 CL005） | 记录（既有测试卫生问题，下批 test 收口时一并清理） |

**OBS-1 详析（非 CL005、非阻断）**：运行全量 pytest 时，`test_dashboard.py::TestDaemonMode::test_daemon_mode_subprocess` 在随机端口启动真实 dashboard daemon（`serve(daemon=True)`）且不 kill，遗留孤儿（PPID=1）。本轮审计跑全量回归 + ops A11 各触发一次，产生孤儿 dashboard（pid 46680 / 端口 60323，本次已清理）；另有一枚既有孤儿（pid 41936 / 端口 54138，2026-09-22 生成，早于本会话，未动）。此测试早于 CL005（commit 8a79b92 `chore@test-docs`），本轮 rework 未触碰 `tests/test_dashboard.py`，与 CL005 判定无关。附带说明：`registry-managed.json`（dashboard 自注册）与 `history.json`（append-only 日志）在跑测试时会产生对应条目，属 managed 服务自身状态/审计日志，非 `registry.json`/`services.json` 污染；上轮审计同现象。

---

## 四、评分

| 维度 | 得分 | 说明 |
|:--|:--|:--|
| SEC-1 闭合 | 通过 | try/except 合入、`_terminate_runner` 回滚、三态报错、退出码 1，T28/T28b + A16 独立复现 |
| R-1/R-2/R-3 处置 | 通过 | 版本元数据 / §9.2+§9.5 计数 / §9.7 口径 全部按期望落地 |
| 回归 | 通过 | 592 passed / 35 passed / 21/21 harness / 31/31 + 13/13 既有 harness |
| 未越界 | 通过 | rework src diff 仅 `__init__`(4) + `server.py`(33)，无 registry.py/MAX_PORT/保留端口 |
| 残留 | 通过 | registry.json 结构身份不变（仅 last_access_at 漂移）、services.json 逐字节一致、locks/ 空、无遗留 START listener/锁 |
| 安全事项 | 0 必改 + 1 🟢 观察 | SEC-1/R-1~R-3 全闭合；OBS-1 非 CL005 非阻断 |

**总分 100 / 100（Rating: A）**

---

## 五、结论

**PASS**。上轮唯一 🟡 必改 SEC-1 已按设计 §2 D3.5 闭合：`registry.add`/`history.add` 合入同一 `try`，异常时先 `_terminate_runner` 终止本次 runner 再按三态报错并 `return False`，经 T28/T28b（monkeypatch 独立复现：终止 + 无孤儿 + 锁释放 + stderr/json 信封）与 ops A16 双重实证；「return False + 三态文案」对「re-raise」的差量判定为语义等价且更贴合 D14 三态（不 dump traceback）。3 项 🟢 记录 R-1/R-2/R-3 全部按期望处置并经独立复算一致。回归 592 passed、35 passed、ops 21/21、既有 harness 31/31+13/13，无回归；rework 越界复核仅含注册段 + 版本元数据；数据目录残留 0（registry.json 结构身份不变、services.json 逐字节一致、locks/ 空）。另有 🟢 OBS-1（既有测试 dashboard daemon 泄漏，非 CL005），不阻断本轮。

按纪律：PASS ⇒ `git commit`（`audit@review:`）+ push。

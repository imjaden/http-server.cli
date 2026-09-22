# HTTP-SERVER-CL003 ops 核查报告（Step 4）

- 件号：`documents/review/http-server-cli-cl003-ops-verify-v1.0-20260922.md`
- 设计依据：`documents/http-server-port-flag-design-v1.1-20260922.md` §8（A 段断言表 A1–A17）
- 被测源码：Step 3 三笔 commit —— `3919da7`（feat@cli）/ `484e0ec`（tests@cli）/ `8f041cd`（docs@sync，含 amend）
- harness：`scripts/port-flag-verify.py`（可复跑，纯标准库）
- 原始结果：`cache/closed-loop/20260922-http-server.cli-HTTP-SERVER-CL003-ops-verify.json`（含逐条 detail）
- 环境：macOS 26.6.2 / host 192.168.31.178 / `hs` = conda py3.12 editable 安装（`src/` 生效）/ 真实 registry 5 服务在跑（含 8080 被 `~/CodeSpace/script-miner/project/macosx` 占用 —— A3 的占用样本）
- 核查日期：2026-09-22

## 1 结论

**31/31 PASS**（A1–A17 含子项），**残留 0**（registry 无 `cl003` 条目、`/tmp` 无 cl003 目录、临时 worktree 已移除）。
复跑命令：

```bash
cd /Users/jadenli/CodeSpace/http-server.cli && python3 scripts/port-flag-verify.py   # 期望：31/31 PASS + 残留 0
```

## 2 逐条结果（实测摘要）

| # | 命令 | 实测 | 判定 |
|:--|:-----|:-----|:--|
| A1 | `hs <dir> -p 8099 -d --url` | rc=0，输出 `http://jaden.local:8099` | PASS |
| A1-b | `hs list --json` 该条 `port` | `port=8099`（path=`/private/tmp/hs-cl003-verify/a1`） | PASS |
| A2 | **修前反证**：worktree 载入 `076d30b` 源码（`PYTHONPATH=<wt>/src`）跑同命令 | rc=0，端口 **8084 ≠ 8099** ⇒ 判据非恒真 | PASS |
| A3 | `hs <dir> -p 8080`（8080 在跑） | rc=**1**；stderr「端口 8080 已被占用（PID 1289 / ~/CodeSpace/script-miner/project/macosx）」+ 换端口提示 | PASS |
| A4-8180 | `hs <dir> -p 8180`（dashboard 未跑） | rc=**1**；「保留端口（dashboard=8180 / mcp=8181），如需启动请用 hs dashboard -p 8180」 | PASS |
| A4-8181 | `hs <dir> -p 8181` | rc=**1**；同上（mcp 侧文案） | PASS |
| A5-区间 | `hs <dir> -p 99` | rc=**2**；`❌ Port must be between 1024-65535` | PASS |
| A5-非法值 | `hs <dir> -p abc` | rc=**2**（修前 rc=0 假成功）；argparse usage 行含 `[-p PORT]` | PASS |
| A6 | `hs <a1dir> --prot 8080`（已运行路径） | rc=0；stderr「未识别参数（已忽略）: --prot 8080」+「指定端口: hs . -p <port>」；stdout **无**该文字 | PASS |
| A6-b | `hs list --prot`（不启动服务路径） | rc=0；同上告警，stdout 零污染 | PASS |
| A7 | `hs <dir> -p 8097 -d --json` | 信封 `data.port=8097`（D7） | PASS |
| A8-1 | `hs -p 8096 -d --url <dir>` | rc=0，`http://jaden.local:8096`，无 `Unknown command`（D8） | PASS |
| A8-2 | `hs -i index.html -p 8095 -d --url <dir>` | rc=0，`:8095`（D8 第二形态：`-i` 取值归位） | PASS |
| A9 | 同目录再启动 + `-p 8500` | rc=0，URL 仍 8099；stderr「已运行在 8099（-p 8500 未生效；如需换端口请先 hs kill 8099）」（D5） | PASS |
| A9-b | registry 该路径条目数 | 1 条且 `port=8099`（未另起实例） | PASS |
| A10-1 | `hs dashboard -p 8280 -d` → `dashboard status --json` | port=8280 | PASS |
| A10-2 | `dashboard restart --port 8290` → status | port=**8290**（修前硬编码 8180，D9a） | PASS |
| A10-3 | `dashboard restart`（无 `--port`）→ status | port=8290（沿用 entry 端口） | PASS |
| A11 | `web add cl003-demo --cmd true --port 9001` → `web cl003-demo --json` | `cmd_effective='true --port 9001'` | PASS |
| A11-b | `web show cl003-demo --json` | 含端口 9001 | PASS |
| A11-c | `web remove cl003-demo` → `web list --json` | 无 cl003-demo（清理完成） | PASS |
| A12 | `grep -rn 不占用终端 src/ skills/ README.md README.zh.md` | 命中 **0** 行（`documents/` 豁免，O3） | PASS |
| A13 | `PYTHONPATH=src pytest tests/ -q` | **535 passed**（基线 490 + 45 新增；0 failed） | PASS |
| A14-1 | `hs version` | `http-server v1.4.0` | PASS |
| A14-2 | grep `__init__.py` / `CHANGELOG.md` / `spec.yaml` | `28:__version__ = '1.4.0'` / `3:## 1.4.0 (2026-09-22)` / `2:version: 1.4.0` | PASS |
| A15-1 | `hs /nonexistent; echo $?` | rc=**1**（修前 0） | PASS |
| A15-2 | `hs kill 59999; echo $?` | rc=**1**（修前 0，D14/R-1） | PASS |
| A15-3 | `hs status 59999; echo $?` | rc=**0**（查询成功，D14 保持） | PASS |
| A16-占用态 | dashboard 在 8180 时 `hs <dir> -p 8180` | rc=1；「8180 为内置服务保留端口（**dashboard 正在使用，PID 35780**），请换端口」（D16 双态） | PASS |
| A16-空闲态 | dashboard 停后 `hs <dir> -p 8180` | rc=1；「如需启动请用 hs dashboard -p 8180」 | PASS |
| A17 | `grep -n 1.3.1 CHANGELOG.md` | `24:- 1.3.1（2026-09-04）为展示名 patch 发布，未单列 CHANGELOG 条目`（F-12 补注在 1.4.0 条目内） | PASS |

## 3 harness 自身缺陷（核查过程中出现并已修，留档）

| # | 现象 | 根因 | 处置 |
|:--|:-----|:-----|:-----|
| H-1 | 首轮 A1-b FAIL（`hs list --json` 查不到刚启动的条目，A9-b 同机制却 PASS） | `hs start` 返回后 registry/`list` 存在数十~数百 ms 写入+存活判定延迟（**harness 竞态，非产品缺陷**：同条目在 A9-b 稳定可查） | `entry_for()` 加重试（8 × 0.4s）；复跑后 A1-b 稳定 PASS |
| H-2 | 首轮 A13 FAIL（rc=1 且 stdout 为空） | harness 以**后台进程**运行时 `sys.executable` 落到不含 pytest 的解释器（skill pitfall #6 同源）；旧实现只取 stdout 尾行 ⇒ 报错信息未被记录 | 增加解释器候选链（`HS_VERIFY_PY` → conda py3.12 → `sys.executable`）并保留 stderr 摘要；复跑命中 py3.12 |

> 两处均为 harness 侧问题，**未改动被测源码**；首轮 29/31 → 修复后连续两轮 **31/31**（第二轮自 `scripts/port-flag-verify.py` 运行，验证可复跑）。

## 4 覆盖边界与未覆盖项（诚实声明）

1. **幂等分支会掩盖 fail-closed 断言**（设计 §13.3-1）：A3/A4/A5 各自使用**不同目录**才可达校验块；同一路径重跑会被幂等分支接走（A9 已专门覆盖该行为）。
2. **A2 的非恒真证明方式**：以 `git worktree` 载入修前 commit `076d30b` 并 `PYTHONPATH` 覆盖运行，未改动当前工作树；实测旧版同命令得 8084（config 8080 被占 → 漂移）。
3. **O1（`is_port_in_use` 裸 bind 无 SO_REUSEADDR）本批不修**：因此 A3 的「占用」样本来自真实在跑服务（8080）；「残留连接导致的**假拒绝**」未构造场景复现，属已知风险（设计 §11 风险行），另批处理。
4. **未覆盖**：`-p` 与 `mcp --port` 的交叉（mcp 端口面未改动）；Windows/Linux 平台差异（本机 macOS only）；`hs dashboard restart --port` 与 mcp 8181 冲突的实测（仅单元测试 `test_restart_rejects_mcp_reserved_port` 覆盖，exit 1）。
5. **registry 影响**：核查过程真实启停 6 个临时服务 + dashboard 两次 + 1 个 web 临时条目，全部清理（残留 0）；核查前后均读取真实 `~/.http-server.cli/`，未见异常条目。

## 5 后续（Step 5）

- 派 review 侧实现审计（prompt：`cache/review-prep/prompt-http-server.cli-20260922-cl003-audit.md`；usage-file：`cache/closed-loop/20260922-http-server.cli-HTTP-SERVER-CL003-audit.json`）。
- 本报告与 harness 由 ops 侧提交（`verify@ops:`）；审计报告 + review-log + `.review-level.yaml` 由 review 侧提交（PASS 后随 `audit@review` 入库 + push）。

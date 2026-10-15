# http-server.cli — web --domain 源头防呆 + 启动横幅修正 设计 v1.0

- 编号：**HTTP-SERVER-CL008**
- 日期：2026-10-15
- 交付版本口径：**1.5.1**（1.5.0 → patch：修正存量数据 + 横幅行为）
- 范围：仅本仓；禁 push（改动只本地提交）

## 1. 现象（用户报现场 + 沙箱复现）

```
$ hs web daily-tracker
❌ 未识别参数: --domain jaden.local
💡 用法: hs start …（运行 hs help 查看全部命令）
✅ Service 'daily-tracker' started
   ⚠️ Cmd exited with code 2
```

沙箱 E2E（HS_DATA_DIR 隔离）：
- use_domain=true + hs cmd → cmd_effective `… -o --domain "localhost"` → status=cmd_failed、exit_code=2、rc=1
- use_domain=false + hs cmd → ✅ 启动成功、rc=0

## 2. 根因定位

| 编号 | 缺陷 | 位置（修前） |
|:--|:--|:--|
| R1 | web-run 无条件注入 `--domain` 到 cmd 末尾，不检查 cmd 是否为 hs 型 | `cli.py:1926-1929` |
| R2 | `hs start` 自身无 `--domain` 参数面 | `cli.py:305-315` |
| R3 | CL007 fail-closed 升级（`cli.py:108-130`）后，注入的未知 flag 导致 exit 2 + 零副作用 → 服务根本没起 | `cli.py:121-126` |
| R4 | 存量 daily-tracker / local.jaden.tech 的 `cmd` 为 `hs` 型 + `use_domain=true` → 必挂 | `services.json` |
| R5 | cmd_failed 时仍打印 `✅ Service '<name>' started`，与紧随的 `⚠️ Cmd exited with code 2` 矛盾 | `cli.py:1959-1964` |

反证：`hs /Users/jadenli/CodeSpace/daily-tracker -i index.html -o`（去掉 --domain）→ rc=0，输出 http://jaden.local:8081（hs 按 config.json 的 domain 生活生效）。

## 3. 决策（X / Y / Z，澄清确认后记录）

| 编号 | 问题 | 决策 | 理由 |
|:--|:--|:--|:--|
| X | 是否给 `hs start` 增 `--domain`？ | **不做，仅登记** | hs 的 domain 是绑定地址，引入一次性 bind 覆盖需独立特性 |
| Y | A2 逃生开关形态？ | **`--force-domain`** | 显式、CLI 惯例、未来兼容 |
| Z | A3 风险标记进 `--json`？ | **进，新字段 `domain_risk`** | 向后兼容只增字段 |

## 4. AC 转交

| 编号 | AC | 交付口径 |
|:--|:--|:--|
| A1 | cmd_failed 时不打印成功横幅 | `❌ Service '<name>' failed (exit N)` stderr；✅ 仅 exit_code=0；JSON 零变更 |
| A2 | `hs web add/update` 在 `use_domain=True` + hs 型 cmd 时 fail-closed | exit 2 + 提示；`--force-domain` 逃生；判定基于解析后首 token |
| A3 | `hs web list/show` 对 hs 型 + use_domain=true 打风险标记 | 人类路径 ⚠️；JSON `domain_risk` 字段 |
| A4 | 文档补 --domain 语义边界 | help / SKILL.md / README / README.zh |
| A5 | 测试 + 四同步 | 新增 test_cl008_web_domain_guard.py；1.5.0→1.5.1；CHANGELOG/features/spec 同步 |
| A6 | ops 清理两条存量 + 真机复跑 | `hs web update daily-tracker --no-domain` / `hs web update local.jaden.tech --no-domain` |

## 5. 测试矩阵

| 测试 | 断言 |
|:--|:--|
| A1: use_domain=true + hs cmd + no --force → rc=1, stderr 含 `failed (exit N)`, stdout 无 `✅` | ✅ |
| A1: use_domain=false + hs cmd → rc=0, stdout 含 `✅` | ✅ |
| A2: add --domain + hs cmd → exit 2 | ✅ |
| A2: add --domain + hs cmd + --force-domain → 成功注册 | ✅ |
| A2: update --domain + hs cmd → exit 2 | ✅ |
| A3: list --json → domain_risk=true | ✅ |
| A3: show → stderr 含 ⚠️ | ✅ |
| A3: show --json → domain_risk | ✅ |
| A3: list --json + non-hs → domain_risk=false/absent | ✅ |

## 6. 变更文件清单

| 文件 | 改动 |
|:--|:--|
| `src/http_server_cli/cli.py` | A1 横幅; A2 防呆+force-domain; A3 风险标记; A4 help |
| `src/http_server_cli/__init__.py` | 版本 1.5.0→1.5.1 |
| `skills/hs-web/SKILL.md` | --domain 语义边界 |
| `README.md` | --domain 说明 |
| `README.zh.md` | --domain 说明 |
| `CHANGELOG.md` | 1.5.1 条目 |
| `features.md` | 测试数同步 |
| `http-server.cli.spec.yaml` | version 1.5.1 |
| `documents/http-server-cl008-*.md` | 本件 |
| `cache/draft/TODO-20261015.md` | READY |

## 7. 非目标（不做）

- 不回退 CL007 fail-closed（正确方向）
- 不给 `hs start` 加 `--domain`（独立特性，已登记 X1）
- 不在只读命令里自动改动注册表（list/show 零副作用）
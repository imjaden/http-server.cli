---
name: hs-web
description: 跨项目 web 服务注册管理 — hs web 命令速查 + 其他模块接入指南（把任意 web 服务注册为 web <name> 一键启动/访问）。任何带 web 服务的项目先读此篇。
---

# hs-web — 跨项目 Web 服务注册管理

## 触发条件

- 你的项目/模块有 web 服务（面板 / 站点 / demo / 本地服务），想用 `web <name>` 统一启动 + 访问
- 需要把任意 CLI 启动命令（不限于 http-server）注册为按名称调用
- 排查 `hs web` 的探测 / `--domain` / open 策略问题
- 评审其他项目是否该接入 hs web（对照推广节）

## 一句话

`hs web` 把「名称 → 任意启动命令」做进注册表（`~/.http-server.cli/services.json`）：
执行 `web <name>` 时，服务已运行 → 直接开浏览器；未运行 → 执行注册的启动命令再访问。
与 `hs bookmark` 的分工：bookmark 管静态目录（`hs start` 专用），`hs web` 管任意命令（跨项目）。

## 命令速查

| 命令 | 说明 |
|------|------|
| `hs web add <name> --cmd '<cmd>' [--url <url>] [--open cmd\|url\|both\|none] [--domain]` | 注册服务（--cmd 必填） |
| `hs web update <name> [--cmd] [--url] [--open] [--domain\|--no-domain]` | 更新（`--url ''` / `--no-domain` 清除） |
| `hs web list [--json]` | 列出所有注册 |
| `hs web show <name>` / `hs web remove <name>` | 详情 / 删除 |
| `hs web <name> [--no-probe]` | 执行：已运行→直接访问；未运行→执行启动命令 |
| `web <name>` | 全局薄壳（`~/.local/bin/web`，`exec hs web "$@"`） |

全部子命令支持 `--json` 信封（command: web-add / web-list / web-show / web-remove / web-update / web-run）。

## 注册要点

- **name** 规则 `[a-zA-Z0-9][a-zA-Z0-9._-]*`（点号可用，如 `daily.checker`）；不得与内置命令或 web 子命令名（add/update/list/show/remove/help）冲突
- **--cmd** 必填，完整命令行字符串（如 `'dk server start --daemon --open'`）；**cmd 需为守护/后台形式**，web 透传执行不阻塞
- **--url** 可选：固定端口服务填 url → web 先探测，可达则幂等直达（不执行 cmd）；**动态端口服务（启动前未知端口）不填** → 直接透传 cmd
- **--open** 开浏览器策略（默认 `url`）：`url`=web 统一开 / `cmd`=命令自带 -o / `both`=都试 / `none`=不开
- **--domain** 布尔：执行时把 `config.json` 的 domain 注入 cmd 末尾（`cmd ... --domain "<domain>"`），适合服务需要绑定域名参数（如 `dk server start --daemon --open` → 追加 `--domain "jaden.local"`）

## 执行语义（hs web <name>）

1. 找不到 name → stderr 报错 + 可用列表 + exit 1
2. 探测阶段（仅当注册了 url 且未 `--no-probe`）：url 可达（urllib，零依赖）→ 直接 open，**不执行 cmd**（幂等）
3. 执行阶段：执行 cmd（`use_domain` 时末尾追加 `--domain "<config.domain>"`）；url/both 策略启动后 wait 就绪（10×0.3s）再 open；cmd 退出码非 0 → stderr warning 不阻断
4. `--no-probe` = 跳过探测，总是执行 cmd（强制重启）

## 推广节：其他模块接入步骤

1. 确认服务的启动命令与固定端口（动态端口就不填 url，open 用 cmd）
2. 注册：`hs web add <name> --cmd '<启动命令>' [--url http://127.0.0.1:<port>] [--open cmd|url] [--domain]`
3. 验证：`hs web <name>` 已运行→直达 / 未运行→启动；`web <name>` 同效
4. 把注册命令写进项目 README / draft，AI session 用 `hs prompt web` 可随时取用

真实实例（本机已注册）：

| 服务 | 注册命令 | 说明 |
|------|----------|------|
| daily-checker 面板 | `hs web add daily.checker --cmd 'dk server start --daemon --open' --url http://127.0.0.1:5001` | 固定端口，open=url：5001 活→直达；没活→dk 启动+开 |
| jaden.tech 站点 | `hs web add jaden.tech --cmd 'hs jaden.tech -o' --open cmd` | 动态端口，无 url：直接透传，命令自带 -o |
| 线上站点（如 llm-radar.jaden.tech） | `hs web add <site> --cmd 'true' --url https://<site>` | 远程服务无需启动：cmd 用 no-op，url 探测直达 |

## 坑

- cmd 前台阻塞命令会卡住 web（注册守护形式，如 `--daemon` / `-d`）
- name 用 web 子命令名（add/show/...）会被拦（SEC-022-1）；services.json 被手工改成非法形状会报 DataCorruptionError（SEC-022-2）
- 探测/打开浏览器只在 `hs web <name>` 执行路径发生；`list/show` 不触发
- 测试隔离注意：conftest monkeypatch 在测试运行时生效，测试代码模块级 `from ... import SERVICES_PATH` 拿到的是真实路径（详见 http-server-ops Pitfall 11）

## 关联

- `hs prompt hs-cli` / `hs prompt hs-bookmark`：http-server 本体与静态目录书签
- http-server-ops skill：hs web 实现细节与 Pitfall 11（conftest import 绑定时机）
- 本功能由 HTTP-SERVER-CL001（基础）+ CL002（--domain + 推广）落地

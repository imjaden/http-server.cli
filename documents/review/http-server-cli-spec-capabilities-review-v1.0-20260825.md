# http-server.cli spec capabilities 补齐 — review报告 v1.0

> 日期: 2026-08-25
> 文件: http-server.cli.spec.yaml (v1.1.0)
> 项目路径: /Users/jadenli/CodeSpace/http-server.cli
> 待 push commit: 7352fbd (docs@spec: add bookmark/mcp/dashboard/registry-managed/range/json/url/glob/migration capabilities)
> review维度: 审计规范执行 / commit规范 / 命名规范(CL-SEC18 闭环 — spec.yaml 补域 T5)

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | capabilities 声明 17 项 = specs 定义 17 项,一一对应,无缺失无冗余 | yaml.safe_load 加载后列表比对 | ✅ PASS (17=17, missing NONE, extra NONE) |
| 2 | capability 命名 kebab-case | 正则 `[a-z0-9]+(-[a-z0-9]+)*` 全量匹配 | ✅ PASS (17/17) |
| 3 | capabilities 无重复项 | Counter 去重检查 | ✅ PASS |
| 4 | 9 新 capability req/scenario 计数与需求声明逐一吻合 | yaml.safe_load 遍历 | ✅ PASS (bookmark 5/11, http-serving 2/5, registry-managed 2/3, dashboard 4/9, mcp-integration 3/6, json-output 2/5, url-flag 1/2, glob-resolution 2/2, data-migration 1/4 = 22 reqs / 47 scenarios) |
| 5 | bookmark 组合键唯一 + --force 覆盖 | 读源码 bookmark.py:94-107 | ✅ PASS ((path, index_page) 组合键;force=True 删除旧条目替换,不覆盖 name 冲突) |
| 6 | bookmark 损坏检测 DataCorruptionError | bookmark.py:23, 49-53 | ✅ PASS (非空文件 JSON 解析失败抛 DataCorruptionError) |
| 7 | bookmark 名称与内置命令冲突 | cli.py:827-833 | ✅ PASS (`parsed.name in _COMMANDS` → 提示冲突) |
| 8 | bookmark 通配符首页原样存储 + 字面量立即校验 | cli.py:846-859 | ✅ PASS (含 `*` 原样存储不展开;字面量走 _validate_index_page) |
| 9 | mcp _TOOLS 6 工具清单 | mcp.py:45-95 | ✅ PASS (hs_list/hs_status/hs_start/hs_kill/hs_kill_all/hs_config,与 spec mcp-02 逐名一致) |
| 10 | mcp initialize 校验(未初始化拒绝 tools/list) | mcp.py:271-272 | ✅ PASS (raise ValueError 'Must call initialize first') |
| 11 | mcp stdio 不登记托管 / SSE 登记 managed | mcp.py:485-488 (serve_stdio 仅 run()),516-518 (daemon 父进程 mreg.add) | ✅ PASS (与 spec mcp-01 两个场景一致) |
| 12 | handler Range 请求 206 + Content-Range + 416 | handler.py:110-131 | ✅ PASS (无 Range→200+Accept-Ranges;有效 Range→206+Content-Range;无效→416) |
| 13 | dashboard /api/* REST 路由 | dashboard.py:108-129 | ✅ PASS (/api/servers, /api/status/{port}, /api/info, /api/ping/{port}, /api/log/{port}) |
| 14 | dashboard 语言切换 /?lang=zh + /en | dashboard.py:85-88, 106-107 | ✅ PASS |
| 15 | dashboard 默认端口 8180 + -p + 子命令 | cli.py:551 (default=8180), 546-548 (stop/status/restart) | ✅ PASS |
| 16 | cli --url 与 --json 互斥 + 仅 URL 输出 | cli.py:172-174 (互斥提示+exit 2), 202-208 (url_only,退出码) | ✅ PASS |
| 17 | json 统一信封 {success, command, data, error} | utils.py:306-322 | ✅ PASS (json_output 四字段结构) |
| 18 | _migrate_legacy_data 自动迁移 4 场景 | utils.py:47-74 | ✅ PASS (旧目录不存在→return;新目录已存在→return;move 失败→copytree 兜底;双失败→警告继续不中断) |
| 19 | kill-all 隔离托管服务 | server.py:620-622 (kill_all 仅遍历 self.registry.all() 用户注册表) | ✅ PASS (managed registry 不触碰) |
| 20 | YAML 语法有效 | yaml.safe_load 加载成功 | ✅ PASS |
| 21 | 全量 pytest | `.venv/bin/python -m pytest tests/ -q` | ✅ PASS (**350 passed in 1.23s**) |
| 22 | src/ 零变更 | `git show 7352fbd --stat` | ✅ PASS (仅 1 文件 http-server.cli.spec.yaml +390 行) |
| 23 | commit 无 /Users 字面路径 | `git show 7352fbd | grep -c "/Users/"` | ✅ PASS (0 hits) |
| 24 | commit 格式 type@scope: subject | `git log -1 --format=%B` | ✅ PASS (docs@spec: subject,scope 非空,type=docs 在枚举集) |
| 25 | dashboard 绑定地址(安全边界) | dashboard.py:521 | ✅ PASS (HTTPServer 绑定 127.0.0.1 loopback) |

## 维度评估

### 一、审计规范执行 — ✅ PASS

- capabilities 声明与 specs 定义一一对应实测 17=17,无缺失无冗余(yaml.safe_load,非人工数数)
- 9 个新 capability 的 req/scenario 与源码行为逐一比对,均能找到实现锚点(bookmark.py / mcp.py / handler.py / dashboard.py / cli.py / utils.py / server.py / registry_managed.py)
- YAML 语法有效 + 全量 pytest 350 passed 实测(venv 环境,非系统 python3)
- 未触碰源码逻辑:commit diff 仅 spec.yaml 单文件 +390 行,src/ 零变更
- 3 件套产出齐备(本报告 + review-log.md + .review-level.yaml)

### 二、commit规范 — ✅ PASS

- subject 格式 `docs@spec: add bookmark/mcp/dashboard/registry-managed/range/json/url/glob/migration capabilities`:type=docs ✓,scope=spec(非空)✓,subject 描述具体功能清单 ✓
- 无 /Users 字面路径(diff 全文 0 hits)✓
- 单一属性分组:纯 spec 文档变更,无代码混入 ✓

### 三、命名规范 — ✅ PASS

- capability 命名 kebab-case 17/17(service-lifecycle, port-allocation, registry-managed, mcp-integration, json-output, url-flag, glob-resolution, data-migration 等)✓
- 无点号、无下划线、无大写 ✓

## 安全事项

🟢 SEC-018-1 — dashboard API 无认证 + Access-Control-Allow-Origin: *

dashboard.py:64 所有 JSON 响应带 `Access-Control-Allow-Origin: *`,/api/kill、/api/restart 等管理端点无认证。但服务绑定 127.0.0.1 loopback(dashboard.py:521),本地单用户开发工具,攻击面仅限本机进程(恶意网页可跨源请求 loopback API)。风险边界明确,记录不阻断。修复建议(可选):CORS 收窄为 `Access-Control-Allow-Origin: http://127.0.0.1:{port}` 或校验 Origin 头。

🟢 SEC-018-2 — bookmark.py:33 docstring 与新组合键语义不一致

bookmark.py:33 类 docstring 仍写"路径唯一约束: 不同 name 不可指向同一 path",与实际组合键语义(同 path 不同 index_page 可并存,bookmark.py:83-84/94-98)矛盾。属 1.0.6~1.1.0 功能演进遗留的过时注释(本次 commit 未触碰 src/)。建议 ops 顺手更新 docstring,不影响本次 spec 审计结论。

## 评分

| 扣分项 | 数量 | 扣分 |
|:-------|:----:|:----:|
| 🔴 HIGH × -15 | 0 | 0 |
| 🟡 MEDIUM × -5 | 0 | 0 |
| 🟢 LOW × 0 | 2 (记录) | 0 |

得分: **100 / 100 → Rating: A (≥85)**

## 结论

**PASS** — CL-SEC18 闭环。spec.yaml 补域 T5 审计通过:capabilities 17=17 一一对应(9 新 + 8 旧),47 个新 scenarios 与源码行为全部一致,pytest 350 passed,src/ 零变更,commit 格式与命名规范合规。2 条 🟢 记录不阻断。→ 执行 git push origin main。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | dashboard CORS 收窄(可选,loopback 边界已明确) | 安全性 🟢 SEC-018-1 |
| □ | bookmark.py:33 docstring 同步组合键语义(随手修) | 文档一致性 🟢 SEC-018-2 |

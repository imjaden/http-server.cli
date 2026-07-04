# GitHub CI Issues 记录

> 涵盖 GitHub Actions (llm-radar) + http-server-cli 脚本的常见问题及解决方案。
> 同类问题已去重合并。

---

## 1. CI 测试环境类

### 1.1 硬编码本机路径

| 项目 | 内容 |
|:---|:---|
| 问题 | `tests/conftest.py` 第 6 行、`tests/test_cli.py` 第 7/16/25 行写死 `/Users/jadenli/CodeSpace/...` |
| 根因 | 开发用 MacBook 绝对路径，未考虑 CI runner 和阿里云服务器的路径差异 |
| 影响 | CI 全部 16 个测试因 `FileNotFoundError` 失败 |
| **解决方案** | `Path(__file__).resolve().parent.parent` 而非固定字符串 |
| 状态 | ✅ 已修复，commit `7bdebd5` |

```diff
-PROJECT_ROOT = Path("/Users/jadenli/CodeSpace/llm-radar.jaden.tech")
+PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

### 1.2 Chrome/chromedriver 未安装

| 项目 | 内容 |
|:---|:---|
| 问题 | `tests/test_selenium.py` 3 个测试在 CI 全部失败 |
| 根因 | CI runner 不预装 Chrome，`/Applications/Google Chrome.app` 不存在 |
| 影响 | CI 多 3 个 FAILED，但 selenium 测试对代码质量验证非必要 |
| **解决方案** | 环境变量 `GITHUB_ACTIONS` 检测到 CI 时自动跳过 |
| 状态 | ✅ 已修复，commit `436c61e` |

```python
pytestmark = pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true",
    reason="CI has no Chrome/chromedriver binaries")
```

### 1.3 DEEPSEEK_API_KEY 未配置

| 项目 | 内容 |
|:---|:---|
| 问题 | workflow 引用了 `secrets.DEEPSEEK_API_KEY`，但仓库 Secrets 中未创建 |
| 根因 | GitHub Secrets 不存在时解析为空字符串，API 调用鉴权失败 |
| 影响 | 集成测试（extract/merge）依赖 API key，运行时 crash |
| **解决方案** | 在 GitHub 仓库设置中创建 Secret |
| 状态 | 🔴 未修复（需你操作） |

```bash
# GitHub 网页操作:
# 仓库 Settings -> Secrets and variables -> Actions
# -> New repository secret
#   Name: DEEPSEEK_API_KEY
#   Secret: 你的 DeepSeek API Key
```

---

## 2. Shell 脚本类 (http-server-cli)

### 2.1 `local` 关键字在函数外使用

| 项目 | 内容 |
|:---|:---|
| 问题 | `script/hs-mcp-demo.sh` 在函数体外使用 `local ver`，bash 报 SyntaxError |
| 根因 | 脚本从函数提取变量到全局作用域时遗漏了 `local` 移除 |
| 影响 | 脚本运行时报错退出 |
| **解决方案** | 删除函数外的 `local` 关键字，或用 `readonly` 替代（仅需赋值一次的场景） |
| 状态 | ⏳ 待处理 |

```bash
# 排查
bash -n script/hs-mcp-demo.sh
grep -n '^[[:space:]]*local ' script/*.sh
```

### 2.2 daemon 模式无限子进程链

| 项目 | 内容 |
|:---|:---|
| 问题 | `serve_sse(port, daemon=True)` 通过 `Popen` 递归调用自身 |
| 根因 | 子进程启动时未传 `--no-daemon` 标志，再次进入 daemon 分支 |
| 影响 | 进程无限 fork，系统资源耗尽 |
| **解决方案** | daemon 分支 spawn 子进程时追加 `--no-daemon` 参数 |
| 状态 | ⏳ 待处理 |

```python
# 修复前
def serve_sse(port, daemon=True):
    if daemon:
        subprocess.Popen(["python3", __file__, "mcp", "--port", str(port)])
        # 子进程又进入 daemon=True

# 修复后
def serve_sse(port, daemon=True):
    if daemon:
        subprocess.Popen(["python3", __file__, "mcp", "--port", str(port), "--no-daemon"])
        return
    _serve_sse(port)
```

---

## 3. MCP Server 类 (llm-radar-mcp-server)

### 3.1 stdio 模式 PID 覆盖

| 项目 | 内容 |
|:---|:---|
| 问题 | 手工启动的 MCP Server 写入 PID，Hermes Agent spawn 的实例覆盖该 PID |
| 根因 | 管道模式（isatty=False）跳过 PID 检查，但 Hermes 子进程是持久管道非一次性 |
| 影响 | `status`/`stop` 只能控制最后一个实例 |
| **解决方案** | 区分"一次性管道"（echo pipe）和"持久子进程"（Hermes spawn）：持久子进程恢复 PID 检查 |
| 状态 | 🟡 已知，待排期 |

### 3.2 HTTP 模式无标准 /mcp 端点

| 项目 | 内容 |
|:---|:---|
| 问题 | `start --port 8901` 提供自定义 REST API，非标准 MCP StreamableHTTP |
| 根因 | HTTP 模式是为手工 curl 测试设计的，未考虑 Hermes Agent 对接需求 |
| 影响 | Hermes Agent `url:` 配置无法直接对接 |
| **解决方案** | 新增 `/mcp` 端点实现 MCP JSON-RPC 2.0 over HTTP，或保持 stdio 对接 |
| 状态 | 🟡 已知，建议方案 A（stdio + HTTP 辅查） |

---

## 4. 数据模型类

### 4.1 merge_entities 无滑动窗口

| 项目 | 内容 |
|:---|:---|
| 问题 | MCP Server 的 `merge_entities()` 不做 100 条上限和 15 天滑动窗口 |
| 根因 | 未同步 Agent Loop 的留存逻辑 |
| 影响 | 热点数量超过 100 条上限 |
| **解决方案** | 在 MCP Server 的 `merge_entities()` 末尾添加与 Agent Loop 相同的留存逻辑 |
| 状态 | ✅ 已修复 |

### 4.2 稀疏字段

| 项目 | 内容 |
|:---|:---|
| 问题 | `ref` / `status` 等字段仅部分实体有值，schema 不统一 |
| 根因 | 两套写入管道（Agent Loop + MCP）字段覆盖不完全 |
| 影响 | 迁移到 Supabase 时需定义 nullable 列 |
| **解决方案** | 统一两套 merge 逻辑的必填字段，清理旧数据中的稀疏字段 |
| 状态 | 🟡 建议迁移前处理 |

---

## 5. 问题总览

| # | 类别 | 问题 | 状态 | 优先级 |
|:---|:---|:---|:---:|:---:|
| 1 | CI 路径 | conftest.py / test_cli.py 硬编码 Mac 路径 | ✅ | P0 |
| 2 | CI 缺少 Chrome | selenium 测试 CI 失败 | ✅ | P1 |
| 3 | CI 缺少 API Key | DEEPSEEK_API_KEY Secret 未配置 | 🔴 **需你操作** | P0 |
| 4 | Bash 写法 | local 在函数外报 SyntaxError | ⏳ | P2 |
| 5 | Daemon 递归 | serve_sse daemon=True 无限 fork | ⏳ | P2 |
| 6 | PID 竞争 | 多实例 stdio 模式 PID 覆盖 | 🟡 | P3 |
| 7 | HTTP 协议 | HTTP 模式无标准 /mcp 端点 | 🟡 | P3 |
| 8 | 数据留存 | MCP merge_entities 无滑动窗口 | ✅ | P2 |

---

## 6. 排查命令汇总

```bash
# CI 硬编码路径
grep -rn '/Users/jadenli' tests/
GITHUB_ACTIONS=true python3 -m pytest tests/ -v --tb=short

# Shell 语法
bash -n script/hs-mcp-demo.sh
grep -n '^[[:space:]]*local ' script/*.sh

# MCP 状态
cat data/mcp-server.pid
curl http://localhost:8901/health

# 数据稀疏字段
python3 -c "
import json
s = json.load(open('data/snapshot.json'))
for dim in ['providers','people','tools','llms','hotspots']:
    items = s.get(dim, [])
    if items:
        all_keys = set()
        for i in items: all_keys.update(i.keys())
        present = {k: sum(1 for i in items if k in i) for k in all_keys}
        sparse = {k:v for k,v in present.items() if v < len(items)}
        if sparse:
            print(f'{dim}: {sparse}')
"
```

---

## 附：文档命名规范头脑风暴

当前涉及的 3 个文档：

| 文档 | 当前命名 | 类型 |
|:---|:---|:---|
| http-server-cli 方案 | `github-ci-cd-recommendation.md` | 设计方案（未来导向） |
| 本文（问题记录） | `github-ci-issues-v1.0-20260704.md` | 问题记录（过去导向） |
| IRIS-Output 惯例 | `{name}-v{major}.{minor}-{YYYYMMDD}.md` | 通用规范 |

### 核心矛盾

```text
http-server-cli 命名:           IRIS-Output 命名:
  github-ci-cd-recommendation.md    github-ci-issues-v1.0-20260704.md
  无版本号后缀                       有版本号+日期后缀
  无分类前缀                         无分类前缀
```

### 推荐规范

按文档类型分为两类，用前缀区分：

| 类型 | 前缀 | 文件名模板 | 示例 |
|:---|:---|:---|:---|
| **设计方案** | (无) | `{domain}-{purpose}.md` | `github-ci-cd-recommendation.md` |
| **问题记录** | `issues` | `{domain}-issues-v{major}.{minor}-{YYYYMMDD}.md` | `github-ci-issues-v1.0-20260704.md` |
| **操作速查** | `ops` | `{domain}-ops-v{major}.{minor}-{YYYYMMDD}.md` | `llm-radar-ops-v1.0-20260625.md` |
| **教程/指南** | `guide` | `{domain}-guide-v{major}.{minor}-{YYYYMMDD}.md` | `hermes-memory-guide-v1.2-20260614.md` |

### 分类依据

- **设计方案** — 推荐架构、实施方案（如 CI/CD 方案），**面向未来**，版本号在文档内
- **问题记录** — 踩坑记录（如本文），**面向过去**，版本号在文件名便于追溯
- **操作速查** — 日常命令（如 llm-radar-ops），**面向现在**，需要快速查找
- **教程/指南** — 知识体系（如 hermes-memory），**面向学习**，版本号在文件名

---

*版本: 1.1 | 更新: 2026-07-04 | 来源: llm-radar CI + http-server-cli + IRIS-Output 实战*

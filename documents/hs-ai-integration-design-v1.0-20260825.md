# hs AI 对接批次一 — prompt 子命令 + MCP 数据工具/Resources + mcp --config 设计 v1.0

日期: 2026-08-25
作者: ops
状态: READY（闭环 CL-SEC20）
版本: 批次一完成后发布 1.2.0（minor）

## 背景

hs 已具备 AI 集成能力：`hs mcp` MCP Server（SSE/stdio，6 工具：hs_list/status/start/kill/kill_all/config，registry-managed 托管）。用户探讨"hs 指令服务与 AI 对接的灵活方式"，确认三方向（批次一）：

1. `hs prompt <skills-name>`：参考 html-gen prompt，输出项目 skill 使用说明，AI agent 一条命令拿完整规范
2. MCP 服务扩展数据类工具（bookmark/history/search）+ MCP Resources 暴露数据
3. `hs mcp --config`：输出 mcpServers 配置片段，主流 AI 工具一行接入

批次二（暂缓）：hs export / hs doctor。

## 决策记录

| 项 | 决策 | 说明 |
|----|------|------|
| 1. hs prompt | 1A | 建 skills/ 4 篇 + prompt 子命令 |
| 2. MCP 数据工具 | 2A | bookmark 3 件套 + history + search（5 工具） |
| 3. MCP Resources | 3A | 暴露 hs://registry / hs://bookmarks / hs://config |
| 4. mcp --config | 4A | 输出 mcpServers 片段 + --json |
| 5. export/doctor | 5C | 批次二暂缓 |
| 6. 批次 | 6A | 批次一：prompt + mcp 数据工具 + mcp --config |
| 7. 版本 | 1A | 批次一完成发布 1.2.0 |
| 8. skills 篇目 | 2A | hs-cli / hs-bookmark / hs-mcp / hs-dashboard |
| 9. MCP 参数 | 3A | 与 CLI 同构（name/path/index_page/force） |
| 10. Resources URI | 4A | hs://registry / hs://bookmarks / hs://config |
| 11. 管线 | 5A | 设计文档先行 + CL-SEC20 review 审计 + push |

## 一、hs prompt 子命令

参考 html-gen.py cmd_prompt（L683-787，已核实实现）。

### SKILLS_DIR 定位

cli.py 位于 `src/http_server_cli/cli.py`，skills/ 在项目根 →
`SKILLS_DIR = Path(__file__).resolve().parents[2] / 'skills'`（cli.py → http_server_cli → src → 项目根）。

### 行为（对齐 html-gen prompt）

| 调用 | 行为 |
|------|------|
| `hs prompt` | 列出全部 skill：name + description（YAML frontmatter）+ references/*.md + 用法 `hs prompt <name>` |
| `hs prompt <name>` | 输出 SKILL.md 全文 + 尾部拼接 references/*.md |
| `hs prompt <name> --brief` | 仅 description + `## ` 章节标题 + references 列表 |
| `hs prompt [<name>] --json` | 信封 `{status,error,data}`；列表 data=[{name,description,references}]；详情 data={name,content,references:{stem:text}} |
| `hs prompt <不存在>` | 非 --json：stderr 报错 + 可用列表 + exit 1；--json：`{status:'error',data:null,error:...}` + exit 1 |
| skills/ 缺失或无 skill | stderr 报错 + exit 1 |

实现：cli.py 新增 `@_register def _cmd_prompt(manager, args)`，约 50 行；argparse 子解析器（`hs prompt` 在 _cmd 分发处注册子命令，参考 `_cmd_mcp` 的子命令模式）。

## 二、skills/ 4 篇 SKILL.md

内容来源：features.md（功能契约事实源）+ cli.py _HELP + 既有设计文档。

| skill | 内容 |
|-------|------|
| hs-cli | 总览：安装（pip install http-server-cli）/ 命令速查（start/list/status/kill/kill-all/history/search/config/set/version/help/dashboard/mcp/bookmark）/ 数据目录 ~/.http-server.cli / --json 信封约定 / 启动方式（-d/-f/-o/-i/--url）/ npm 同名注记 |
| hs-bookmark | 书签系统：add/update/remove/list/show、组合键 (path, index_page)、--force 覆盖、--json |
| hs-mcp | MCP 服务：SSE（127.0.0.1:8765/sse）与 stdio、11 工具清单、Resources 3 项、mcpServers 接入配置（hs mcp --config） |
| hs-dashboard | Web 面板：启动（hs dashboard -o）、路由（/api/*、/en）、?lang=zh、默认端口 8180、托管状态管理 |

每篇 SKILL.md 带 YAML frontmatter（name/description），description 供 `hs prompt` 列表展示。

## 三、MCP 扩展

### 5 个新工具

| 工具 | description | input_schema | _TOOL_MAP |
|------|------------|--------------|-----------|
| hs_bookmark_list | 列出所有书签（名称/路径/首页） | {} | (['bookmark','list'], {}) |
| hs_bookmark_add | 注册书签（组合键 (name,path,index_page)，--force 覆盖） | {name:str req, path:str, index_page:str, force:bool} | (['bookmark','add','{name}','{path}'], {'name':'name','path':'path','index_page':'index','force':'force'}) |
| hs_bookmark_remove | 删除书签 | {name:str req} | (['bookmark','remove','{name}'], {'name':'name'}) |
| hs_history | 历史启动记录 | {} | (['history'], {}) |
| hs_search | 模糊搜索运行中的服务 | {keyword:str req} | (['search','{keyword}'], {'keyword':'keyword'}) |

### _build_hs_args 扩展 boolean flag 支持

现有 _build_hs_args（L202-218）只处理值替换。新增：模板项为 `--{key}` 形态且 param_map 映射到布尔参数时，值为 True 才追加。
实现：在模板遍历前预处理——`template` 中若存在 `--force` 固定项，检查 `params.get('force')` 为 True 才保留，否则剔除（bookmark add 用）。通用化：支持 `{--force:force}` 占位语法或约定 `--` 前缀固定项 + 布尔检查。
设计采用最小改动：_TOOL_MAP 模板允许 `--flag` 固定项，_build_hs_args 对 `--` 前缀项检查对应 param_map 键（无则保留）。bookmark_add 的模板 `['bookmark','add','{name}','{path}','--force']` + param_map {'force':'force'} → val True 才追加 `--force`。

### MCP Resources

MCP 协议 capabilities 增加 `'resources': {}`；_dispatch 增加 `resources/list` + `resources/read`：

| URI | 内容 |
|-----|------|
| hs://registry | 运行中服务 registry（读 ~/.http-server.cli/registry.json） |
| hs://bookmarks | 书签数据（读 ~/.http-server.cli/bookmarks.json） |
| hs://config | 配置（执行 `hs config --json` 输出） |

resources/list 返回 3 项（uri/name/description）；resources/read 返回 {contents:[{uri,mimeType:'application/json',text:...}]}。文件不存在返回空 JSON `{}`（不报错）。

### SERVER_VERSION 同步

SERVER_VERSION '1.0.0' → '1.1.0'（MCP 服务能力扩展）。

## 四、hs mcp --config

`_cmd_mcp` 增加子命令 `--config`（argparse add_argument('--config', action='store_true')）：
- 非 --json：输出 mcpServers YAML 片段：
  ```
  mcpServers:
    hs:
      command: hs
      args: ["mcp"]
      transport: stdio
  ```
- --json：信封 data={mcpServers:{hs:{command:'hs',args:['mcp'],transport:'stdio'}}}
- 同时输出备注（SSE 方式：hs mcp 默认 SSE → http://127.0.0.1:8765/sse）
- 不影响现有子命令（start/stop/status/restart）；`hs mcp --stdio` 已存在（serve_stdio）

## 五、版本 1.2.0

- src/http_server_cli/__init__.py `__version__ = '1.2.0'`
- CHANGELOG 新增 1.2.0 条目（prompt 子命令 / MCP 5 工具 + Resources / mcp --config）
- features.md：CLI 命令数 +1（prompt）、MCP 工具 6→11、测试数同步

## 六、测试计划

- 新增 tests/test_prompt.py：skills/ 4 篇存在且 frontmatter 合法；hs prompt 无参列表（name 齐全）；详情含全文；--brief 含章节；--json 信封正常/错误路径（不存在 exit≠0 + status:error）；skills 缺失场景（monkeypatch SKILLS_DIR）
- 扩展 tests/test_mcp.py：tools/list 返回 11 工具；hs_bookmark_add 参数映射（force=True → 含 --force；force 缺省 → 无 --force）；resources/list 3 项；resources/read 各 URI 返回 JSON
- 全量 pytest 零回归（当前 357 + 新增）

## 七、commit 分组

1. docs@design: hs-ai-integration-design-v1.0-20260825.md
2. docs@skills: skills/ 4 篇 SKILL.md（hs-cli/hs-bookmark/hs-mcp/hs-dashboard）
3. feat@prompt: hs prompt 子命令 + tests/test_prompt.py
4. feat@mcp: MCP 5 工具 + Resources + hs mcp --config + tests 扩展
5. docs@changelog: 1.2.0 版本 + CHANGELOG + features.md 同步

## 风险与边界

- prompt 子命令不触碰源码逻辑；skills/ 为文档产物（docs 性质）
- MCP 新工具只操作用户 registry/bookmark 数据，不碰 registry-managed（CL-SEC18 边界原则）
- Resources 读取为只读，无写操作；文件缺失容错
- _build_hs_args 扩展需回归现有 6 工具映射（kill 特例 L196-200 不变）
- 不修改其他 profile 数据；.hermes-project.yaml 既有 M 不纳入 commit

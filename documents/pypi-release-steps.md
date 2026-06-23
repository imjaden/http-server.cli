# http-server-cli PyPI 发布流程

> 本文档说明如何将 http-server-cli 发布到 PyPI，以及涉及到的项目文件结构和关键文档处理。
>
> 路径：本文档位于 `documents/pip-release-steps.md`，不纳入 git 版本管理。

---

## 一、项目文件结构（标注 pip 发布涉及情况）

```
http-server-cli/
├── pyproject.toml                 # ✅ 涉及 — 发布核心配置
├── MANIFEST.in                    # ✅ 涉及 — sdist 包含哪些额外文件
├── README.md                      # ✅ 涉及 — PyPI 首页（中文版，默认使用）
├── README.en.md                   # ✅ 涉及 — PyPI 首页（英文版，需手动切换）
├── LICENSE                        # ✅ 涉及 — MIT 协议，必须包含
├── http-server-cli.spec.yaml      # ❌ 不涉及 — 本地规格说明，sdist 包含但不影响发布
│
├── src/http_server_cli/
│   ├── __init__.py                # ✅ 涉及 — 版本号来源（`__version__`）
│   ├── __main__.py                # ❌ 不涉及 — `python -m` 入口，自动包含
│   ├── cli.py                     # ❌ 不涉及
│   ├── config.py                  # ❌ 不涉及
│   ├── handler.py                 # ❌ 不涉及
│   ├── registry.py                # ❌ 不涉及
│   ├── runner.py                  # ❌ 不涉及
│   ├── server.py                  # ❌ 不涉及
│   └── utils.py                   # ❌ 不涉及
│
├── tests/                         # ❌ 不涉及 — sdist 包含但不影响发布
│
├── cache/                         # ❌ 不涉及 — 本地文档，不纳入 git
│   └── pip-release-steps.md       #     ← 本文档（已迁移至 documents/）
│
├── dist/                          # ✅ 涉及 — 构建产物目录（gitignore 忽略）
│   ├── http-server-cli-1.0.x.tar.gz
│   └── http_server_cli-1.0.x-py3-none-any.whl
│
├── .gitignore                     # ❌ 不涉及 — 控制 git，不影响发布
└── setup.sh                       # ❌ 不涉及 — 本地 alias 安装，不发布
```

---

## 二、关键文档逐一说明

### 1. `pyproject.toml` — 发布核心配置

```toml
[project]
name = "http-server-cli"                           # PyPI 包名，全网唯一
dynamic = ["version"]                               # 版本号从 __init__.py 读取
description = "本地 HTTP 服务管理器"                # 一句话描述（PyPI 列表页显示）
readme = "README.md"                                # PyPI 首页内容来源
requires-python = ">=3.7"
license = "MIT"
authors = [{name = "Jaden Li"}]
keywords = ["http-server", "static-server", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",               # 发布前改为 5 - Production/Stable
    "Operating System :: MacOS",
    "Natural Language :: Chinese (Simplified)",     # 中文 → 英文发布时改为 English
]

[project.urls]
Homepage = "https://github.com/imjaden/http-server-cli"  # PyPI 页面上的链接

[project.scripts]
hs = "http_server_cli.cli:main"                     # 安装后可执行命令

[tool.setuptools.dynamic]
version = {attr = "http_server_cli.__version__"}    # 从源码读取版本号

[tool.setuptools.package-data]
"*" = ["*.spec.yaml"]                               # sdist 包含 spec 文件
```

**发布前需检查：**
- [ ] `name` 未与 PyPI 上已有包冲突（`pip install http-server-cli` 应先验证可用）
- [ ] `classifiers` 中的 `Development Status` 是否合适
- [ ] `description` 是否与 README 语言一致
- [ ] `readme` 指向正确的文件（中文→`README.md`，英文→`README.en.md`）

---

### 2. `__init__.py` — 版本号单一来源

```python
__version__ = '1.0.x'  # 发版时更新
```

`pyproject.toml` 通过 `[tool.setuptools.dynamic] version = {attr = "..."}` 读取此值。

**发布前需检查：**
- [ ] 版本号已更新（遵循语义化版本：主版本.次版本.修订号）
- [ ] 与上一次发布相比版本号递增

---

### 3. `MANIFEST.in` — sdist 额外文件清单

```
include http-server-cli.spec.yaml   # 规格说明书
include README.md                    # PyPI 首页（当前使用中文版）
include pyproject.toml               # 构建配置
```

sdist（`.tar.gz`）默认只包含 Python 源码文件，`MANIFEST.in` 声明需要额外打包的文件。

**发布前需检查：**
- [ ] 如果切换为英文版 README，此处需改为 `include README.en.md`
- [ ] 新增的配置文件是否需要加入

---

### 4. `README.md` / `README.en.md` — PyPI 首页

PyPI 将 `readme` 字段指向的文件内容渲染为包首页。内容包括：

- 项目 slogan 和一句话介绍
- 安装命令
- 用法示例（日常三件事）
- 所有命令速查表
- 数据目录 / 平台要求 / 本地开发

**语言选择（参见第三节）：**

| 使用场景 | `pyproject.toml` 中 `readme` 值 | 实际使用的文件 |
|:---------|:-------------------------------|:---------------|
| 中文用户为主（默认） | `readme = "README.md"` | `README.md` |
| 英文用户为主（PyPI 国际） | `readme = "README.en.md"` | `README.en.md` |

---

### 5. `LICENSE` — 开源协议

当前使用 **MIT License**。文件必须存在，PyPI 会检测并在页面展示协议信息。`pyproject.toml` 中 `license = "MIT"` 应与 LICENSE 文件内容一致。

---

## 三、调整 README 为英文版发布

### 3.1 修改步骤

总共需改 4 处：

```bash
# 1. pyproject.toml — 指向英文 README
#    修改 readme = "README.md" → readme = "README.en.md"

# 2. pyproject.toml — 修改描述和分类器
#    修改 description = "本地 HTTP 服务管理器" → description = "Local HTTP Server Manager"
#    修改 classifier "Natural Language :: Chinese (Simplified)" 
#         → "Natural Language :: English"

# 3. MANIFEST.in — 确保英文 README 被打包
#    新增一行: include README.en.md

# 4. 构建并验证
python3 -m build
python3 -m twine check dist/*
```

### 3.2 切换前后的差异对照

| 项目 | 中文版（默认） | 英文版 |
|:-----|:--------------|:-------|
| `readme` 指向 | `README.md` | `README.en.md` |
| `description` | `"本地 HTTP 服务管理器"` | `"Local HTTP Server Manager"` |
| 分类器 | `Chinese (Simplified)` | `English` |
| `MANIFEST.in` | `include README.md` | `include README.en.md` + `include README.md` |
| PyPI 首页语言 | 中文 | 英文 |

### 3.3 完整切换命令

```bash
# 更新 pyproject.toml
# readme = "README.md" → readme = "README.en.md"
# description 改为英文
# classifier 改为 English

# 更新 MANIFEST.in — 添加 README.en.md
echo "include README.en.md" >> MANIFEST.in

# 清理旧构建
rm -rf dist/ build/

# 构建
python3 -m build

# 检查
python3 -m twine check dist/*

# 发布
python3 -m twine upload dist/*
```

**注意：** 切换前确保 `README.en.md` 内容与 `README.md` 保持同步（功能变更时两边都要更新）。

---

## 四、完整发布流程速查

> **前置条件：** 确保 `~/.pypirc` 已配置 TestPyPI 和 PyPI 的 API token（参见 §5.1）。

```bash
# 一键发布（推荐）
bash scripts/release-pypi.sh -t   # 先发布到 TestPyPI 验证
bash scripts/release-pypi.sh      # 发布到正式 PyPI

# 或手动分步执行：
#
# 0. 前置条件
pip install build twine
#
# 1. 更新版本号
#    编辑 src/http_server_cli/__init__.py → __version__
#
# 2. 检查清单
#    □ 版本号已递增
#    □ 所有测试通过（python3 -m pytest tests/ -v）
#    □ pyproject.toml 配置正确（readme 指向正确的文件）
#    □ MANIFEST.in 包含需要的文件
#    □ README 内容已更新（中英文同步）
#
# 3. 构建
rm -rf dist/ build/
python3 -m build
python3 -m twine check dist/*
#
# 4. 发布到 TestPyPI（可选）
python3 -m twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ http-server-cli
hs version
#
# 5. 发布到 PyPI
python3 -m twine upload dist/*
#
# 6. 验证
pip install --upgrade http-server-cli
hs version
hs . -o
```

---

## 五、常见问题

### 5.1 ~/.pypirc — PyPI 认证配置

`~/.pypirc` 是 [Python 官方规范](https://packaging.python.org/en/latest/specifications/pypirc/) 的发布认证文件，用于存储 PyPI 和 TestPyPI 的 API token。

**格式：**

```ini
[testpypi]
  username = __token__
  password = pypi-xxxxxxxxxxxx

[pypi]
  username = __token__
  password = pypi-yyyyyyyyyyyy
```

- key-value 行允许前导缩进
- `password = xxx` 中间允许空格
- 发布脚本 `scripts/release-pypi.sh` 会自动读取对应 section 的 password

**生成 token：**

| 平台 | 地址 |
|------|------|
| TestPyPI | https://test.pypi.org/manage/account/token/ |
| PyPI | https://pypi.org/manage/account/token/ |

---

### 5.2 版本已存在（File already exists）

PyPI 和 TestPyPI 均**不允许覆盖已存在的版本**。这是安全设计——防止攻击者用同版本号替换恶意代码。

```
ERROR    HTTPError: 400 Bad Request
         File already exists ('http_server_cli-1.0.x-py3-none-any.whl')
```

**解决办法：**

```bash
# 唯一方案：升版本号重发
# 编辑 src/http_server_cli/__init__.py
__version__ = '1.0.x'  # 递增

# 重新构建发布
bash scripts/release-pypi.sh -t   # 先 TestPyPI 验证
```

TestPyPI 允许在 Web UI 删除版本，但**删除后版本号仍不能重用**（文件名 hash 被记录）。

---

### 5.3 镜像源同步延迟

新包发布到 pypi.org 后，国内镜像源（清华 tuna、阿里云、豆瓣等）**不会实时同步**。

| 镜像源 | 典型延迟 |
|--------|---------|
| pypi.org（官方） | 立即 |
| 清华 tuna | 15分钟 ~ 数小时 |
| 阿里云 | 30分钟 ~ 数小时 |
| 豆瓣 | 1小时 ~ 24小时 |

**验证方法：**

```bash
# 官方源确认已存在
pip install http-server-cli -i https://pypi.org/simple/

# 查看官方源版本列表
pip index versions http-server-cli -i https://pypi.org/simple/

# 查看 tuna 是否已同步
pip index versions http-server-cli -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

**首次发布最慢**（镜像源需要发现新包名）。后续更新会更快（15-30 分钟）。

# GitHub CI/CD 推荐方案

> 版本: 1.0
> 更新: 2026-06-29
> 项目: http-server-cli

## 方案 A：GitHub Actions — 自动 Release + PyPI 发布

### 工作流文件位置

`.github/workflows/release.yml`

### 触发条件

```yaml
on:
  push:
    tags:
      - 'v*'           # 推送 v1.0.8, v1.1.0 等标签时触发
```

### 工作流步骤

| 步骤 | 说明 |
|:-----|:------|
| 1. Checkout | 拉取源码 |
| 2. 设置 Python | 3.12 环境 |
| 3. 安装依赖 | `pip install build twine` |
| 4. 运行测试 | `python -m pytest tests/ -q` |
| 5. 构建 | `python -m build` |
| 6. 创建 GitHub Release | 自动生成 changelog + 上传 dist/*.whl |
| 7. 发布到 PyPI | `twine upload dist/*`（需配置 PyPI Token） |

### 所需 Secrets

| Secret 名 | 用途 | 获取方式 |
|:----------|:-----|:---------|
| `PYPI_TOKEN` | PyPI 发布权限 | https://pypi.org/manage/account/token/ → "Add API token" → 作用域选 "Entire account" 或具体项目 → 复制 token 字符串 |

### 配置步骤（详细）

1. 打开 PyPI → https://pypi.org/manage/account/token/ → "Add API token"
   - Token name: `http-server-cli-github-actions`
   - Scope: 选择项目 `http-server-cli`（推荐）或 "Entire account"
   - 创建后 **立即复制** token 字符串（只显示一次）
2. 打开 GitHub 仓库 → `Settings` → `Secrets and variables` → `Actions`
   - 点击 `New repository secret`
   - Name: `PYPI_TOKEN`
   - Secret: 粘贴上一步复制的 token
   - 点击 `Add secret`

### 完整 YAML

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install build twine
      - run: python -m pytest tests/ -q
      - run: python -m build
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: dist/*
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

## 方案 B（可选）：自动测试 PR

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: python -m pytest tests/ -q
```

## 实施步骤

1. 按上方「配置步骤」在 PyPI 创建 token + GitHub 添加 `PYPI_TOKEN` Secret
2. 确认 `.github/workflows/release.yml` 已存在且内容正确
3. 推送到 main 分支
4. 打 tag 触发自动发布: `git tag v1.0.8 && git push --tags`

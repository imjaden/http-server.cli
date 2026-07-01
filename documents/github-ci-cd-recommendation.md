# GitHub CI/CD 推荐方案

> 版本: 1.1
> 更新: 2026-07-01
> 项目: http-server-cli

## GitHub Actions — 自动 Release + PyPI 发布

### 工作流文件位置

`.github/workflows/release.yml`

### 触发条件

```yaml
on:
  push:
    tags:
      - 'v*'           # 推送 v1.0.8, v1.1.0 等标签时触发
```

### 工作流架构

```
tag push
    │
test-and-build (测试 + 构建 wheel)
    ├──► publish-testpypi (TestPyPI 验证，可选)
    └──► release (GitHub Release + PyPI 发布)
```

`publish-testpypi` 和 `release` 在 `test-and-build` 成功后并行执行，互不阻塞。

### 工作流步骤

| 步骤 | 说明 |
|:-----|:------|
| 1. Checkout | 拉取源码 |
| 2. 设置 Python | 3.12 环境 |
| 3. 安装依赖 | `pip install build twine pytest` |
| 4. 安装项目 | `pip install -e .` |
| 5. 运行测试 | `python -m pytest tests/ -q` |
| 6. 构建 wheel | `python -m build` |
| 7. 上传构建产物 | `actions/upload-artifact` 供下游 job 使用 |
| 8. (可选) 发布 TestPyPI | `twine upload --repository testpypi` — 验证包结构 |
| 9. 创建 GitHub Release | 自动生成 changelog + 上传 `dist/*.whl` |
| 10. 发布到 PyPI | `twine upload dist/*` |

### 所需 Secrets

| Secret 名 | 用途 | 获取方式 |
|:----------|:-----|:---------|
| `PYPI_TOKEN` | PyPI 发布权限 | https://pypi.org/manage/account/token/ → "Add API token" |
| `TESTPYPI_TOKEN` | TestPyPI 发布权限（可选） | https://test.pypi.org/manage/account/token/ → "Add API token" |

TestPyPI 是可选步骤（`continue-on-error: true`），不配置 `TESTPYPI_TOKEN` 不影响正式发布。

### 完整 YAML

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  test-and-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install build twine pytest
      - run: pip install -e .
      - run: python -m pytest tests/ -q
      - run: python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish-testpypi:
    needs: test-and-build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - run: twine upload --repository testpypi dist/*
        continue-on-error: true
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.TESTPYPI_TOKEN }}

  release:
    needs: test-and-build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: dist/*
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

## 可选方案：自动测试 PR

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
      - run: pip install pytest
      - run: pip install -e .
      - run: python -m pytest tests/ -q
```

## TestPyPI 配置步骤

1. 打开 https://test.pypi.org/manage/account/token/ → "Add API token"
   - Token name: `http-server-cli-github-actions-test`
   - 创建后复制 token
2. GitHub 仓库 → `Settings` → `Secrets and variables` → `Actions`
   - `New repository secret` → Name: `TESTPYPI_TOKEN` → 粘贴 token
3. 下次发版时，`publish-testpypi` job 会自动执行验证

> TestPyPI 的包名与 PyPI 相同，版本号建议使用类似 `1.0.8.dev1` 的格式避免冲突。
> 实际发布流程：TestPyPI 验证通过后，再决定是否正式发布到 PyPI。

## 实施步骤

1. 按上方配置步骤创建 PyPI token + GitHub Secrets
2. 确认 `.github/workflows/release.yml` 已存在且内容正确
3. 推送到 main 分支
4. 打 tag 触发自动发布: `git tag v1.0.8 && git push origin v1.0.8`

---

## Git Tag 使用指南

### 查看 tag

```bash
git tag                          # 列出所有本地 tag
git tag -l 'v1.0.*'              # 按模式过滤
git tag --sort=-version:refname  # 按版本号降序
git tag -n                       # 列出 tag + 附注信息
```

### 创建 tag

```bash
git tag v1.0.8                   # 轻量 tag（推荐，仅指针）
git tag -a v1.0.8 -m "release"   # 附注 tag（含作者/日期/消息）
```

### 推送 / 删除 tag

```bash
git push origin v1.0.8           # 推送单个 tag ✅ 推荐
git push origin --tags           # 推送所有本地未推送的 tag ⚠️ 慎用

git tag -d v1.0.8                # 删除本地 tag
git push origin --delete v1.0.8  # 删除远程 tag
```

### 检出 tag

```bash
git checkout v1.0.8              # 切换到 tag 指向的 commit（detached HEAD）
git checkout -b hotfix v1.0.8    # 从 tag 创建分支做紧急修复
```

### 常用场景速查

| 场景 | 命令 |
|:-----|:------|
| 发版后打 tag | `git tag v1.0.8 && git push origin v1.0.8` |
| 补打之前的 commit | `git tag v1.0.7 <commit-sha>` |
| 确认当前版本对应哪个 tag | `git describe --tags` |
| 查看两个版本之间的提交 | `git log v1.0.7..v1.0.8 --oneline` |
| 比较两个版本的代码差异 | `git diff v1.0.7..v1.0.8 --stat` |
| 回滚到某个发布版本 | `git checkout v1.0.7` |

### 工作流示意

```text
开发 → 测试通过 → bump 版本号 → commit
→ git tag v1.0.8               # 本地打 tag
→ git push origin v1.0.8       # 推送 tag → GitHub Actions 自动 Release + PyPI
```

### tag 打错位置？重打

如果 tag 指向了错误的 commit，可以删除重打：

```bash
git tag -d v1.0.8              # 删除本地 tag
git push origin --delete v1.0.8  # 删除远程 tag
# 切到正确的 commit 重新打
git tag v1.0.8                 # 在 HEAD（最新 commit）上打 tag
git push origin v1.0.8         # 推送新 tag → 触发 CI/CD
```

也可以用 `git tag v1.0.8 <commit-sha>` 在任意提交上打 tag。

> **Actions 运行状态查看**：<https://github.com/imjaden/http-server-cli/actions>
>
> 注意：`git push` 推送代码和 `git push origin <tag>` 推送 tag 是两个独立操作。
> 只有推送 tag 才会触发 `.github/workflows/release.yml` 中的 `on: push: tags: ['v*']` 条件。

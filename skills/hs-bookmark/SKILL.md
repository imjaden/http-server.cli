---
name: hs-bookmark
description: 书签系统 — add/update/list/show/remove、组合键 (path,index_page)、--force 覆盖、通配符 index、--json。
---

# hs-bookmark — 书签系统

## 简介

书签 = 命名的路径（+ 可选首页），`hs <name>` 一键启动常用项目。
唯一键为 `(path, index_page)` 组合：同一路径不同首页可注册多个书签。

## 命令

```bash
# 注册书签（path 默认当前目录）
hs bookmark add alpha ~/project-alpha
hs bookmark add alpha ~/project-alpha -i index.html
hs bookmark add alpha ~/project-alpha -i 'snapshots/*.html'   # 通配符，运行时取 max(mtime)
hs bookmark add alpha ~/project-alpha --force                  # 覆盖组合键冲突

# 更新
hs bookmark update alpha ~/project-beta -i app.html

# 查看
hs bookmark list                 # 列出所有
hs bookmark show alpha           # 详情

# 删除
hs bookmark remove alpha

# 全部支持 --json 信封
hs bookmark list --json
```

## 启动书签

```bash
hs alpha -o        # 等价 hs start ~/project-alpha -o
```

## 关键语义

1. **组合键唯一**：`(path, index_page)` 冲突时报错；`--force` 覆盖组合键冲突（不覆盖 name 冲突）
2. **通配符 index**：`-i 'snapshots/*.html'` 存原始 pattern，启动时取 `max(mtime)` 的文件
3. **损坏检测**：bookmarks.json 非空但 JSON 解析失败 → `DataCorruptionError`
4. **数据文件**：`~/.http-server.cli/bookmarks.json`

## JSON 信封示例

```json
{"success": true, "command": "bookmark-list", "data": {"bookmarks": [{"name": "alpha", "path": "~/project-alpha", "index_page": null}]}, "error": null}
```

## 关联文档

- documents/bookmark-feature-design-v1.1-20250715.md
- documents/bookmark-multi-page-design-v1.1-20260819.md

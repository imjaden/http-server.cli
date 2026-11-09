# AGENTS.md — http-server.cli 会话约定

## 本仓定位

http-server（CLI 名 `hs`，PyPI 包 `http-server-cli`）：本地静态预览服务 + 服务注册与页面入口（`hs web`）。
站点：https://http-server.cli.jaden.tech

## 回话规范

- 回话规范：`~/CodeSpace/hermes-manager/skills-governance/message-feedback-spec.md`（优先于本文件）。
- 本文件只补本仓特有事实（服务注册、页面入口、CL 闭环等）；形状类约定（首行时间锚、结论先行、四段式、四类停问、降噪）一律遵上述规范，不在此重复。

## 引用与维护

- 规范正文只存一处（hermes-manager），本仓仅保留指针，不复制正文、不新增 skill 副本。
- 本仓特有约定（服务注册、页面入口、CL 闭环等）一律在本文件追加，不另开 AGENTS/约定文件。
- 改本文件：path-scoped `git add AGENTS.md`，单笔提交，subject 用 `docs@agents: <verb …>`。

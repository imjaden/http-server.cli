# -*- coding: utf-8 -*-
"""
双源防漂移测试 — index.html / index.zh.html

两个落地页是独立副本（EN/ZH 文案必然不同），但功能特征必须同步。
本测试纯文件断言：核对两页的关键功能特征一致（结构特征、非文案），
防止只改一页导致的漂移。参考 pages-index 双源防漂移模式。

不引入 Selenium —— 页面是静态落地页，纯文件级断言足够。

结构演进（2026-08-25）:
- 第一轮: 两屏 hero + quick-start + scroll-hint + cmd-row 卡片 + favicon + npm 注记
- 第二轮: 第1屏两列 QUICK START | COMPARISON / 第2屏场景网格 3 列
- 第三轮: 对齐 html-gen page-index 结构 — hero-title / hero-tagline /
  hero-blocks / templates-title / templates-sub / template-grid / back-top / site-footer
"""

from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
INDEX_EN = PROJECT / "index.html"
INDEX_ZH = PROJECT / "index.zh.html"

# 结构特征（与文案无关，双页必须一致）
STRUCTURE_FEATURES = [
    'class="toolbar"',
    'id="themeBtn"',
    'aria-pressed="false"',
    'class="github-corner"',
    'class="hero"',
    'hero-title',
    'hero-tagline',
    'class="install-box"',
    'class="copy-btn"',
    'hero-blocks',
    'hero-block',
    'block-title',
    'class="code-block"',
    'scroll-bounce',
    'flex: 1 1 340px',
    'max-width: 1024px',
    'class="table-wrap"',
    'class="cmd-row"',
    'class="scroll-hint"',
    'class="group-title"',
    'hs bookmark',
    'hs dashboard',
    'hs mcp',
    'class="templates"',
    'id="templates"',
    'templates-title',
    'templates-sub',
    'template-grid',
    'back-top-link',
    'grid-template-columns: repeat(3, 1fr)',
    'npm-note',
    'class="favicon"',
    'site-footer',
    'id="top"',
    'data-copy=',
    'updateHeroHeight',
    'http-server.cli.jaden.tech',
]

pytestmark = pytest.mark.spec("index")


def _read(page: Path) -> str:
    """读取落地页源码（UTF-8）。"""
    assert page.exists(), f"{page.name} 不存在"
    return page.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def _pages():
    return {"en": _read(INDEX_EN), "zh": _read(INDEX_ZH)}


class TestDualSourceSync:
    """index.html 与 index.zh.html 功能特征必须同步。"""

    def test_both_pages_exist(self):
        assert INDEX_EN.exists() and INDEX_ZH.exists()

    def test_structure_features_in_both(self, _pages):
        """每个结构特征必须同时出现在双页。"""
        missing = []
        for feat in STRUCTURE_FEATURES:
            if feat not in _pages["en"] or feat not in _pages["zh"]:
                missing.append(feat)
        assert not missing, f"双页缺失结构特征: {missing}"

    def test_scenario_group_count_equal(self, _pages):
        """场景组标题数必须一致（Start/Bookmark/View/Kill/Manage = 5，Bookmark 并入 Start 卡、Manage 并入 Kill 卡）。"""
        en = _pages["en"].count('class="group-title"')
        zh = _pages["zh"].count('class="group-title"')
        assert en == zh, f"组数不一致: EN={en} ZH={zh}"
        assert en == 5, f"预期 5 组标题, 实际 {en}"

    def test_cmd_row_count_equal(self, _pages):
        """命令行数一致：首屏 quick start 用 code-block（4），场景区用 cmd-row（14）。"""
        en_cmd = _pages["en"].count('class="cmd-row"')
        zh_cmd = _pages["zh"].count('class="cmd-row"')
        assert en_cmd == zh_cmd == 14, f"场景 cmd-row 数量不一致: EN={en_cmd} ZH={zh_cmd}"
        en_cb = _pages["en"].count('<div class="code-block">')
        zh_cb = _pages["zh"].count('<div class="code-block">')
        assert en_cb == zh_cb == 4, f"首屏 code-block 数量不一致: EN={en_cb} ZH={zh_cb}"

    def test_hero_quickstart_and_scrollhint_present(self, _pages):
        """两屏要素: hero / code-block 命令 / scroll-hint(带动画) / 动态高度 JS 双页齐全。"""
        for page in (_pages["en"], _pages["zh"]):
            assert 'class="hero"' in page
            assert 'class="code-block"' in page
            assert 'class="scroll-hint"' in page
            assert 'scroll-bounce' in page
            assert 'updateHeroHeight' in page
            assert "window.innerHeight - 55" in page

    def test_code_block_copy_buttons(self, _pages):
        """首屏每条 code-block 命令带行内复制按钮（6A 保留逐条复制能力）。"""
        for page in (_pages["en"], _pages["zh"]):
            assert page.count('class="code-block"') == 4
            assert page.count('class="copy-btn"') >= 5  # install 1 + code-block 4 + 场景区

    def test_compare_table_rows_equal(self, _pages):
        """对比表行数一致（1 表头 + 5 工具 = 6 行）。"""
        en = _pages["en"].count("<tr>")
        zh = _pages["zh"].count("<tr>")
        assert en == zh, f"对比表行数不一致: EN={en} ZH={zh}"
        assert en == 6, f"预期 6 行(含表头), 实际 {en}"

    def test_bookmark_and_manage_groups_present(self, _pages):
        """Bookmark 与 Manage/管理 组均存在（非回归防护）。"""
        assert "hs bookmark add" in _pages["en"]
        assert "hs bookmark add" in _pages["zh"]
        assert "hs mcp" in _pages["en"]
        assert "hs mcp" in _pages["zh"]

    def test_title_full_name(self, _pages):
        """title 使用全称（HTTP Server，2026-08-25 手工微调定案；hs 缩写仅保留在命令/图标/对比行名）。"""
        for name, page in (("en", _pages["en"]), ("zh", _pages["zh"])):
            assert "<title>HTTP Server" in page, f"{name} title 未用全称 HTTP Server"
            assert "<title>hs" not in page, f"{name} title 仍以 hs 缩写开头"

    def test_page_index_structure_aligned(self, _pages):
        """与 html-gen page-index 规范对齐的结构要素双页齐全。"""
        for page in (_pages["en"], _pages["zh"]):
            assert 'class="hero-title"' in page
            assert 'class="hero-tagline"' in page
            assert 'class="hero-blocks"' in page
            assert 'class="hero-block' in page
            assert 'class="templates"' in page
            assert 'id="templates"' in page
            assert 'class="templates-title"' in page
            assert 'class="templates-sub"' in page
            assert 'class="template-grid"' in page
            assert 'class="back-top-link"' in page
            assert 'class="site-footer"' in page
            assert 'id="top"' in page
            assert 'href="#templates"' in page  # scroll-hint 指向第二屏

    def test_hero_title_gradient(self, _pages):
        """hero-title 渐变标题（--hero-title-from/to 变量，浅色对比度）。"""
        for page in (_pages["en"], _pages["zh"]):
            assert "--hero-title-from" in page
            assert "--hero-title-to" in page
            assert "linear-gradient(180deg" in page
            assert "background-clip: text" in page

    def test_template_grid_breakpoints(self, _pages):
        """template-grid 1200px + 1500/1100 断点 + 组卡片化双页一致。"""
        for page in (_pages["en"], _pages["zh"]):
            assert "max-width: 1200px" in page
            assert "@media (max-width: 1500px)" in page  # 3列→2列
            assert "@media (max-width: 1100px)" in page  # 2列→1列
            assert "border-radius: 10px" in page  # 组卡片化

    def test_theme_js_sync_in_both(self, _pages):
        """主题 JS 的 aria-pressed 同步逻辑双页一致。"""
        en_ok = "btn.setAttribute('aria-pressed'" in _pages["en"]
        zh_ok = "btn.setAttribute('aria-pressed'" in _pages["zh"]
        assert en_ok and zh_ok, "aria-pressed 同步逻辑缺失"

    def test_no_stale_github_link(self, _pages):
        """落地页不残留旧仓库链接（http-server-cli 无点形态）。"""
        for page in (_pages["en"], _pages["zh"]):
            assert "github.com/imjaden/http-server-cli" not in page, "残留旧链接"

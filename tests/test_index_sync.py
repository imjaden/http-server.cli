# -*- coding: utf-8 -*-
"""
双源防漂移测试 — index.html / index.zh.html

两个落地页是独立副本（EN/ZH 文案必然不同），但功能特征必须同步。
本测试纯文件断言：核对两页的关键功能特征一致（结构特征、非文案），
防止只改一页导致的漂移。参考 pages-index 双源防漂移模式。

不引入 Selenium —— 页面是静态落地页，纯文件级断言足够。
"""

from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
INDEX_EN = PROJECT / "index.html"
INDEX_ZH = PROJECT / "index.zh.html"

# 结构特征（与文案无关，双页必须一致）
# 两屏重构（2026-08-25）后新增: hero 两屏 / quick-start / scroll-hint /
# cmd-row 命令卡片 / favicon 图标 / npm 注记 / 动态高度 JS
# 第二轮（2026-08-25）: 第1屏两列 quick-compare(qs-col|cmp-col) / 第2屏 scenarios-grid
STRUCTURE_FEATURES = [
    'class="toolbar"',
    'id="themeBtn"',
    'aria-pressed="false"',
    'class="github-corner"',
    'class="hero"',
    'class="install-box"',
    'class="copy-btn"',
    'class="quick-start"',
    'class="quick-compare"',
    'class="qs-col"',
    'class="cmp-col"',
    'class="table-wrap"',
    'class="cmd-row"',
    'class="scroll-hint"',
    'class="group-title"',
    'hs bookmark',
    'hs dashboard',
    'hs mcp',
    'scenarios-grid',
    'grid-template-columns: repeat(3, 1fr)',
    'npm-note',
    'class="favicon"',
    'data-copy=',
    'updateHeroHeight',
    '<footer>',
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
        """scenarios 组数必须一致（当前 5 组: Start/View/Kill/Bookmark/Manage）。"""
        en = _pages["en"].count('class="group-title"')
        zh = _pages["zh"].count('class="group-title"')
        assert en == zh, f"组数不一致: EN={en} ZH={zh}"
        assert en == 5, f"预期 5 组, 实际 {en}"

    def test_cmd_row_count_equal(self, _pages):
        """命令卡片行数一致（quick start 4 + 场景 14 = 18），兼作两屏结构漂移哨兵。"""
        en = _pages["en"].count('class="cmd-row"')
        zh = _pages["zh"].count('class="cmd-row"')
        assert en == zh, f"cmd-row 数量不一致: EN={en} ZH={zh}"
        assert en == 18, f"预期 18 行(quick start 4 + 场景 14), 实际 {en}"

    def test_hero_quickstart_and_scrollhint_present(self, _pages):
        """两屏要素: hero / quick-start / scroll-hint / 动态高度 JS 双页齐全。"""
        for page in (_pages["en"], _pages["zh"]):
            assert 'class="hero"' in page
            assert 'class="quick-start"' in page
            assert 'class="scroll-hint"' in page
            assert 'updateHeroHeight' in page
            assert "window.innerHeight - 110" in page

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
        """title 使用全称 http-server（2026-08-25 第二轮: hs 缩写仅保留在命令/图标/对比行名）。"""
        for name, page in (("en", _pages["en"]), ("zh", _pages["zh"])):
            assert "<title>http-server" in page, f"{name} title 未用全称 http-server"
            assert "<title>hs" not in page, f"{name} title 仍以 hs 缩写开头"

    def test_two_column_screen1(self, _pages):
        """第1屏两列容器（QUICK START | COMPARISON）双页齐全。"""
        for page in (_pages["en"], _pages["zh"]):
            assert 'class="quick-compare"' in page
            assert 'class="qs-col"' in page
            assert 'class="cmp-col"' in page
            assert 'class="table-wrap"' in page
            assert "flex: 0 0 45%" in page  # qs-col 45% / cmp-col 55% 决策

    def test_scenarios_grid_cards(self, _pages):
        """第2屏场景组多列网格 + 组卡片化双页一致。"""
        for page in (_pages["en"], _pages["zh"]):
            assert 'scenarios-grid' in page
            assert "grid-template-columns: repeat(3, 1fr)" in page
            assert "@media (max-width: 1100px)" in page  # 3列→2列断点
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
